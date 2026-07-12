/*
 * ===========================================================================
 *  DataDrivenProtocol.h
 *  Biblioteca compartilhada: protocolo serial + maquina de estados do
 *  controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6), genérica
 *  para N estados e M entradas. Cada placa (firmware/boards/<planta>) so
 *  precisa fornecer os hooks de hardware via PlantIO -- esta biblioteca
 *  nunca conhece pinos, calibracao ou limites fisicos.
 *
 *  Uso tipico em um board (src/main.cpp):
 *
 *    #include <DataDrivenProtocol.h>
 *    void readSensors(float y[N]) { ... }
 *    void setActuators(const float uDesired[M], float uApplied[M]) { ... }
 *    bool overSafetyLimit(const float y[N]) { ... }
 *    void allOff() { ... }
 *
 *    DataDrivenProtocol<N, M> dd({readSensors, setActuators,
 *                                  overSafetyLimit, allOff});
 *    void setup() { dd.begin(115200); }
 *    void loop()  { dd.poll(); }
 *
 *  A excitacao du(k) NAO e enviada pelo PC nem armazenada em RAM: o
 *  firmware a gera sob demanda com um PRNG determinístico (Xorshift32,
 *  ver Xorshift32.h) semeado pelo campo <seed> do CFG. Isso remove o unico
 *  array O(T) que existia (o antigo buffer du_[M][T_CAP]) -- a janela T
 *  deixa de ser limitada pela RAM do Arduino.
 *
 *  Protocolo serial: 115200 baud, linhas ASCII terminadas em '\n'
 *   PC -> Arduino:
 *     CFG,<T>,<dt_ms>,<n>,<m>,<ubar_1..ubar_m>,<settle_s>,<amp_entrada>,<seed>
 *     GO
 *     K,<K_11..K_1n,K_21..K_mn>,<Tsp_1..Tsp_n>,<ctrl_s>   (K linha-major, m x n)
 *     X                                                    aborta a qualquer momento
 *   Arduino -> PC:
 *     ACK,CFG | ACK,GO | ACK,K
 *     S,<t_s>,<y_1..y_n>            streaming do assentamento (1 Hz)
 *     EQ,<ybar_1..ybar_n>           equilibrio medido
 *     D,<k>,<t_ms>,<y_1..y_n>,<u_1..u_m>   amostra do experimento (t_ms =
 *                                   millis() reais desde o inicio do
 *                                   EXPERIMENT -- permite ao PC medir o dt
 *                                   REALMENTE alcancado, ja que dt_ms e so
 *                                   um alvo: se o processamento do passo
 *                                   (leitura + Serial.print) demorar mais
 *                                   que dt_ms, o laço fica limitado pelo
 *                                   tempo de execucao, nao pelo relogio.
 *                                   u=nan,..,nan no ultimo k
 *     WAITK                         dados enviados, aguardando K
 *     C,<t_s>,<y_1..y_n>,<u_1..u_m> streaming do controle em tempo real
 *     END | ERR,<msg>
 * ===========================================================================
 */

#pragma once

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

#include "Xorshift32.h"

template <int N, int M>
class DataDrivenProtocol {
public:
  struct PlantIO {
    void (*readSensors)(float y[N]);
    // aplica uDesired (pode estar fora dos limites fisicos) e escreve em
    // uApplied[] o valor REALMENTE aplicado (ja com saturacao do atuador).
    void (*setActuators)(const float uDesired[M], float uApplied[M]);
    bool (*overSafetyLimit)(const float y[N]);
    void (*allOff)();
  };

  explicit DataDrivenProtocol(PlantIO io) : io_(io) {}

  void begin(unsigned long baud) {
    Serial.begin(baud);
    Serial.println(F("TCLAB-DD,READY"));
  }

  void poll() {
    while (Serial.available()) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') {
        if (blen_ > 0) {
          buf_[blen_] = '\0';
          handleLine(buf_);
          blen_ = 0;
        }
      } else if (blen_ < sizeof(buf_) - 1) {
        buf_[blen_++] = c;
      }
    }

    unsigned long now = millis();

    if (state_ == SETTLE) {
      tickSettle(now);
    } else if (state_ == EXPERIMENT) {
      tickExperiment(now);
    } else if (state_ == CONTROL) {
      tickControl(now);
    }
  }

private:
  enum State { IDLE, READY, SETTLE, EXPERIMENT, WAITK, CONTROL };

  PlantIO io_;
  State state_ = IDLE;

  long Tlen_ = 0;
  unsigned long dt_ms_ = 4000;
  float ubar_[M] = {0};
  unsigned long settle_ms_ = 0;
  float ampEntrada_ = 0.0f;
  Xorshift32 rng_;  // gera du(k) sob demanda -- sem buffer O(T) em RAM

  float K_[M][N] = {{0}};
  float Tsp_[N] = {0};
  unsigned long ctrl_ms_ = 0;

  unsigned long t0_ = 0, nextTick_ = 0, lastSettleMsg_ = 0;
  unsigned long tExpStart_ = 0;  // instante (millis) do inicio do EXPERIMENT, para D,<k>,<t_ms>,...
  long kstep_ = 0;
  float ybarAcc_[N] = {0};
  int ybarN_ = 0;
  float ybar_[N] = {0};

  char buf_[80];
  byte blen_ = 0;

  bool safetyStop(const float y[N]) {
    if (io_.overSafetyLimit(y)) {
      io_.allOff();
      Serial.print(F("ERR,OVERLIMIT"));
      for (int i = 0; i < N; i++) {
        Serial.print(F(","));
        Serial.print(y[i], 2);
      }
      Serial.println();
      state_ = IDLE;
      return true;
    }
    return false;
  }

  void handleLine(char *line) {
    char *tok = strtok(line, ",");
    if (tok == nullptr) return;

    if (strcmp(tok, "X") == 0) {
      io_.allOff();
      state_ = IDLE;
      Serial.println(F("END"));
      return;
    }

    if (strcmp(tok, "CFG") == 0) {
      Tlen_ = atol(strtok(nullptr, ","));
      dt_ms_ = (unsigned long)atol(strtok(nullptr, ","));
      int nIn = atoi(strtok(nullptr, ","));
      int mIn = atoi(strtok(nullptr, ","));
      if (nIn != N || mIn != M) {
        Serial.println(F("ERR,NM_MISMATCH"));
        return;
      }
      for (int i = 0; i < M; i++) ubar_[i] = atof(strtok(nullptr, ","));
      settle_ms_ = (unsigned long)atol(strtok(nullptr, ",")) * 1000UL;
      ampEntrada_ = atof(strtok(nullptr, ","));
      rng_ = Xorshift32((uint32_t)atol(strtok(nullptr, ",")));
      if (Tlen_ <= 0) {
        Serial.println(F("ERR,T_INVALIDO"));
        return;
      }
      state_ = READY;
      Serial.println(F("ACK,CFG"));
      return;
    }

    if (strcmp(tok, "GO") == 0 && state_ == READY) {
      float uApplied[M];
      io_.setActuators(ubar_, uApplied);
      t0_ = millis();
      lastSettleMsg_ = 0;
      for (int i = 0; i < N; i++) ybarAcc_[i] = 0;
      ybarN_ = 0;
      state_ = SETTLE;
      Serial.println(F("ACK,GO"));
      return;
    }

    if (strcmp(tok, "K") == 0 && state_ == WAITK) {
      for (int i = 0; i < M; i++)
        for (int j = 0; j < N; j++)
          K_[i][j] = atof(strtok(nullptr, ","));
      for (int i = 0; i < N; i++) Tsp_[i] = atof(strtok(nullptr, ","));
      ctrl_ms_ = (unsigned long)atol(strtok(nullptr, ",")) * 1000UL;
      t0_ = millis();
      nextTick_ = t0_;
      state_ = CONTROL;
      Serial.println(F("ACK,K"));
      return;
    }
  }

  void tickSettle(unsigned long now) {
    if (now - lastSettleMsg_ < 1000UL) return;
    lastSettleMsg_ = now;

    float y[N];
    io_.readSensors(y);
    if (safetyStop(y)) return;

    unsigned long el = now - t0_;
    Serial.print(F("S,"));
    Serial.print(el / 1000UL);
    for (int i = 0; i < N; i++) {
      Serial.print(F(","));
      Serial.print(y[i], 2);
    }
    Serial.println();

    if (settle_ms_ >= 10000UL && el >= settle_ms_ - 10000UL) {
      for (int i = 0; i < N; i++) ybarAcc_[i] += y[i];
      ybarN_++;
    }

    if (el >= settle_ms_) {
      for (int i = 0; i < N; i++)
        ybar_[i] = (ybarN_ > 0) ? (ybarAcc_[i] / ybarN_) : y[i];
      Serial.print(F("EQ"));
      for (int i = 0; i < N; i++) {
        Serial.print(F(","));
        Serial.print(ybar_[i], 3);
      }
      Serial.println();
      kstep_ = 0;
      nextTick_ = now;
      tExpStart_ = now;
      state_ = EXPERIMENT;
    }
  }

  void tickExperiment(unsigned long now) {
    if ((long)(now - nextTick_) < 0) return;

    float y[N];
    io_.readSensors(y);
    if (safetyStop(y)) return;

    if (kstep_ < Tlen_) {
      float uDesired[M], uApplied[M];
      for (int j = 0; j < M; j++) {
        float duVal = rng_.uniform(-ampEntrada_, ampEntrada_);
        uDesired[j] = ubar_[j] + duVal;
      }
      io_.setActuators(uDesired, uApplied);

      Serial.print(F("D,"));
      Serial.print(kstep_);
      Serial.print(F(","));
      Serial.print(now - tExpStart_);
      for (int i = 0; i < N; i++) {
        Serial.print(F(","));
        Serial.print(y[i], 3);
      }
      for (int j = 0; j < M; j++) {
        Serial.print(F(","));
        Serial.print(uApplied[j], 3);
      }
      Serial.println();
      kstep_++;
      nextTick_ += dt_ms_;
    } else {
      Serial.print(F("D,"));
      Serial.print(kstep_);
      Serial.print(F(","));
      Serial.print(now - tExpStart_);
      for (int i = 0; i < N; i++) {
        Serial.print(F(","));
        Serial.print(y[i], 3);
      }
      for (int j = 0; j < M; j++) Serial.print(F(",nan"));
      Serial.println();

      float uApplied[M];
      io_.setActuators(ubar_, uApplied);  // segura o equilibrio enquanto o PC calcula
      state_ = WAITK;
      Serial.println(F("WAITK"));
    }
  }

  void tickControl(unsigned long now) {
    if ((long)(now - nextTick_) < 0) return;

    float y[N];
    io_.readSensors(y);
    if (safetyStop(y)) return;

    float uDesired[M];
    for (int i = 0; i < M; i++) {
      float acc = ubar_[i];
      for (int j = 0; j < N; j++) acc += K_[i][j] * (y[j] - Tsp_[j]);
      uDesired[i] = acc;
    }
    float uApplied[M];
    io_.setActuators(uDesired, uApplied);

    unsigned long el = now - t0_;
    Serial.print(F("C,"));
    Serial.print(el / 1000.0, 1);
    for (int i = 0; i < N; i++) {
      Serial.print(F(","));
      Serial.print(y[i], 3);
    }
    for (int i = 0; i < M; i++) {
      Serial.print(F(","));
      Serial.print(uApplied[i], 3);
    }
    Serial.println();
    nextTick_ += dt_ms_;

    if (ctrl_ms_ > 0 && el >= ctrl_ms_) {
      io_.allOff();
      state_ = IDLE;
      Serial.println(F("END"));
    }
  }
};
