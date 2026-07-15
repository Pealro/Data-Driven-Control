/*
 * ===========================================================================
 *  DataDrivenProtocol.h
 *  Biblioteca compartilhada: protocolo serial + maquina de estados do
 *  controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6). Cada placa
 *  (firmware/boards/<planta>) so precisa fornecer os hooks de hardware via
 *  PlantIO -- esta biblioteca nunca conhece pinos, calibracao ou limites
 *  fisicos.
 *
 *  N, M sao a CAPACIDADE MAXIMA de estados/entradas que a placa suporta
 *  (dimensiona os arrays). O numero REALMENTE usado num experimento (n <= N,
 *  m <= M) vem do CFG e fica em active_n()/active_m() -- placas com hardware
 *  fisicamente fixo (ex.: tclab_siso, N=M=1) sempre recebem n=N, m=M, entao
 *  o comportamento delas nao muda. Placas "genericas" (ex.: firmware/boards/
 *  generic, N=M=4) podem rodar experimentos com menos canais do que a
 *  capacidade maxima -- os hooks recebem active_n/active_m para saber
 *  quantos canais IGNORAR (evita, por ex., ler ruido de um pino analogico
 *  nao conectado e disparar overSafetyLimit por engano).
 *
 *  Uso tipico em um board (src/main.cpp):
 *
 *    #include <DataDrivenProtocol.h>
 *    void readSensors(float y[N], int active_n) { ... }
 *    void setActuators(const float u_desired[M], float u_applied[M], int active_m) { ... }
 *    bool overSafetyLimit(const float y[N], int active_n) { ... }
 *    void allOff() { ... }
 *
 *    DataDrivenProtocol<N, M> protocol({readSensors, setActuators,
 *                                        overSafetyLimit, allOff});
 *    void setup() { protocol.begin(115200); }
 *    void loop()  { protocol.poll(); }
 *
 *  A excitacao delta_u(k) NAO e enviada pelo PC nem armazenada em RAM: o
 *  firmware a gera sob demanda com um PRNG determinístico (Xorshift32,
 *  ver Xorshift32.h) semeado pelo campo <seed> do CFG. Isso remove o unico
 *  array O(T) que existia (o antigo buffer de excitacao) -- a janela T
 *  deixa de ser limitada pela RAM do Arduino.
 *
 *  Protocolo serial: 115200 baud, linhas ASCII terminadas em '\n'
 *   PC -> Arduino:
 *     CFG,<T>,<dt_ms>,<n>,<m>,<ubar_1..ubar_m>,<settle_duration_s>,<excitation_amplitude>,<seed>
 *     GO
 *     K,<K_11..K_1n,K_21..K_mn>,<setpoint_1..setpoint_n>,<control_duration_s>   (K linha-major, m x n)
 *     SP,<setpoint_1..setpoint_n>                          atualiza o setpoint em tempo real
 *                                                           (so valido durante CONTROL, nao
 *                                                           reinicia o timing nem o ganho K)
 *     XCTRL,<dt_ms>,<control_duration_s>                   controle pautado pelo PC (a lei
 *                                                           roda no PC -- Koopman/delay-embedding);
 *                                                           aceito em WAITK, paralelo ao K
 *     URAW,<u_1..u_m>                                      comando cru a aplicar agora (resposta
 *                                                           ao EC; so valido durante EXTCONTROL)
 *     X                                                    aborta a qualquer momento
 *   Arduino -> PC:
 *     ACK,CFG | ACK,GO | ACK,K | ACK,SP | ACK,XCTRL
 *     EC,<t_ms>,<y_1..y_n>,<u_aplicado_anterior_1..m>      medida do controle pautado pelo PC
 *                                                           (lock-step: firmware espera um URAW
 *                                                           antes da proxima medida). Watchdog:
 *                                                           ERR,EXT_TIMEOUT se o PC sumir.
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
 *     C,<t_ms>,<y_1..y_n>,<u_1..u_m> streaming do controle em tempo real
 *                                   (t_ms = millis() reais desde o K, mesma
 *                                   logica de precisao do t_ms em D acima --
 *                                   nao usa mais 1 casa decimal em segundos)
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
    void (*readSensors)(float y[N], int active_n);
    // aplica u_desired (pode estar fora dos limites fisicos) e escreve em
    // u_applied[] o valor REALMENTE aplicado (ja com saturacao do atuador).
    // Only os primeiros active_m canais importam neste experimento.
    void (*setActuators)(const float u_desired[M], float u_applied[M], int active_m);
    bool (*overSafetyLimit)(const float y[N], int active_n);
    void (*allOff)();
  };

  explicit DataDrivenProtocol(PlantIO io) : io_(io) {}

  void begin(unsigned long baud) {
    Serial.begin(baud);
    // Leonardo (ATmega32u4, USB nativo): espera a porta USB conectar antes de
    // anunciar READY, senao a mensagem se perde. No Uno, Serial e sempre "true"
    // (chip USB-serial separado), entao sai na hora. Timeout de 5s para nao
    // travar se ninguem conectar.
    unsigned long start = millis();
    while (!Serial && (millis() - start) < 5000UL) {}
    Serial.println(F("TCLAB-DD,READY"));
  }

  void poll() {
    while (Serial.available()) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') {
        if (line_buffer_length_ > 0) {
          line_buffer_[line_buffer_length_] = '\0';
          handleLine(line_buffer_);
          line_buffer_length_ = 0;
        }
      } else if (line_buffer_length_ < sizeof(line_buffer_) - 1) {
        line_buffer_[line_buffer_length_++] = c;
      }
    }

    unsigned long now = millis();

    if (state_ == SETTLE) {
      tickSettle(now);
    } else if (state_ == EXPERIMENT) {
      tickExperiment(now);
    } else if (state_ == CONTROL) {
      tickControl(now);
    } else if (state_ == EXTCONTROL) {
      tickExtControl(now);
    }
  }

private:
  // EXTCONTROL: controle pautado pelo PC (lei calculada no PC -- ex.: Koopman
  // racional ou delay-embedding, que nao cabem no ATmega). Lock-step: manda
  // EC,<t>,<y..>,<u_aplicado_anterior..>, espera URAW,<u..>, aplica, pauta o
  // proximo tick por millis(). Ver tickExtControl / handleLine (XCTRL, URAW).
  enum State { IDLE, READY, SETTLE, EXPERIMENT, WAITK, CONTROL, EXTCONTROL };

  // se o PC parar de mandar URAW por mais que isto, desliga tudo (rede de
  // seguranca do controle pautado pelo PC -- ex.: PC travou/desconectou)
  static const unsigned long EXT_WATCHDOG_MS = 3000UL;

  PlantIO io_;
  State state_ = IDLE;

  int active_n_ = N;  // estados REALMENTE usados neste experimento (<= N)
  int active_m_ = M;  // entradas REALMENTE usadas neste experimento (<= M)

  long T_ = 0;  // numero de passos do experimento (janela de excitacao)
  unsigned long dt_ms_ = 4000;
  float ubar_[M] = {0};
  unsigned long settle_duration_ms_ = 0;
  float excitation_amplitude_ = 0.0f;
  Xorshift32 rng_;  // gera delta_u(k) sob demanda -- sem buffer O(T) em RAM

  float K_[M][N] = {{0}};
  float setpoint_[N] = {0};
  unsigned long control_duration_ms_ = 0;

  // estado do EXTCONTROL
  bool ext_awaiting_u_ = false;          // ja mandou EC, esperando URAW do PC
  unsigned long ext_last_c_ms_ = 0;      // quando mandou o ultimo EC (watchdog)
  float u_applied_prev_[M] = {0};        // ultimo u realmente aplicado (p/ log alinhado)

  unsigned long phase_start_ms_ = 0, next_tick_ms_ = 0, last_settle_message_ms_ = 0;
  unsigned long experiment_start_ms_ = 0;  // inicio do EXPERIMENT, para D,<k>,<t_ms>,...
  long sample_index_ = 0;                  // k
  float ybar_accumulator_[N] = {0};
  int ybar_sample_count_ = 0;
  float ybar_[N] = {0};

  char line_buffer_[80];
  byte line_buffer_length_ = 0;

  bool safetyStop(const float y[N]) {
    if (io_.overSafetyLimit(y, active_n_)) {
      io_.allOff();
      Serial.print(F("ERR,OVERLIMIT"));
      for (int i = 0; i < active_n_; i++) {
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
    char *token = strtok(line, ",");
    if (token == nullptr) return;

    if (strcmp(token, "X") == 0) {
      io_.allOff();
      state_ = IDLE;
      Serial.println(F("END"));
      return;
    }

    if (strcmp(token, "CFG") == 0) {
      T_ = atol(strtok(nullptr, ","));
      dt_ms_ = (unsigned long)atol(strtok(nullptr, ","));
      int received_n = atoi(strtok(nullptr, ","));
      int received_m = atoi(strtok(nullptr, ","));
      if (received_n <= 0 || received_n > N || received_m <= 0 || received_m > M) {
        Serial.println(F("ERR,NM_INVALIDO"));
        return;
      }
      active_n_ = received_n;
      active_m_ = received_m;
      for (int i = 0; i < M; i++) ubar_[i] = 0;  // zera canais inativos (evita valor de sessao anterior)
      for (int i = 0; i < active_m_; i++) ubar_[i] = atof(strtok(nullptr, ","));
      settle_duration_ms_ = (unsigned long)atol(strtok(nullptr, ",")) * 1000UL;
      excitation_amplitude_ = atof(strtok(nullptr, ","));
      rng_ = Xorshift32((uint32_t)atol(strtok(nullptr, ",")));
      if (T_ <= 0) {
        Serial.println(F("ERR,T_INVALIDO"));
        return;
      }
      state_ = READY;
      Serial.println(F("ACK,CFG"));
      return;
    }

    if (strcmp(token, "GO") == 0 && state_ == READY) {
      float u_applied[M] = {0};
      io_.setActuators(ubar_, u_applied, active_m_);
      phase_start_ms_ = millis();
      last_settle_message_ms_ = 0;
      for (int i = 0; i < N; i++) ybar_accumulator_[i] = 0;
      ybar_sample_count_ = 0;
      state_ = SETTLE;
      Serial.println(F("ACK,GO"));
      return;
    }

    if (strcmp(token, "K") == 0 && state_ == WAITK) {
      for (int i = 0; i < active_m_; i++)
        for (int j = 0; j < active_n_; j++)
          K_[i][j] = atof(strtok(nullptr, ","));
      for (int i = 0; i < active_n_; i++) setpoint_[i] = atof(strtok(nullptr, ","));
      control_duration_ms_ = (unsigned long)atol(strtok(nullptr, ",")) * 1000UL;
      phase_start_ms_ = millis();
      next_tick_ms_ = phase_start_ms_;
      state_ = CONTROL;
      Serial.println(F("ACK,K"));
      return;
    }

    if (strcmp(token, "SP") == 0 && state_ == CONTROL) {
      for (int i = 0; i < active_n_; i++) setpoint_[i] = atof(strtok(nullptr, ","));
      Serial.println(F("ACK,SP"));
      return;
    }

    // XCTRL,<dt_ms>,<control_duration_s> -- entra no controle pautado pelo PC.
    // Aceito em WAITK (fim da coleta), paralelo ao K: reusa active_n_/active_m_/
    // ubar_ ja definidos pelo CFG. Segura ubar ate o 1o URAW chegar.
    if (strcmp(token, "XCTRL") == 0 && state_ == WAITK) {
      dt_ms_ = (unsigned long)atol(strtok(nullptr, ","));
      control_duration_ms_ = (unsigned long)atol(strtok(nullptr, ",")) * 1000UL;
      float u_tmp[M] = {0};
      io_.setActuators(ubar_, u_tmp, active_m_);
      for (int i = 0; i < active_m_; i++) u_applied_prev_[i] = u_tmp[i];
      phase_start_ms_ = millis();
      next_tick_ms_ = phase_start_ms_;
      ext_awaiting_u_ = false;
      state_ = EXTCONTROL;
      Serial.println(F("ACK,XCTRL"));
      return;
    }

    // URAW,<u_1..u_m> -- o PC manda o comando cru a aplicar agora (resposta ao
    // EC anterior). So valido enquanto o firmware espera (ext_awaiting_u_).
    if (strcmp(token, "URAW") == 0 && state_ == EXTCONTROL && ext_awaiting_u_) {
      float u_desired[M] = {0}, u_applied[M] = {0};
      for (int i = 0; i < active_m_; i++) u_desired[i] = atof(strtok(nullptr, ","));
      io_.setActuators(u_desired, u_applied, active_m_);
      for (int i = 0; i < active_m_; i++) u_applied_prev_[i] = u_applied[i];
      ext_awaiting_u_ = false;
      next_tick_ms_ += dt_ms_;  // proxima medida dt depois do EC que originou este URAW
      return;
    }
  }

  void tickSettle(unsigned long now) {
    if (now - last_settle_message_ms_ < 1000UL) return;
    last_settle_message_ms_ = now;

    float y[N];
    io_.readSensors(y, active_n_);
    if (safetyStop(y)) return;

    unsigned long elapsed_ms = now - phase_start_ms_;
    Serial.print(F("S,"));
    Serial.print(elapsed_ms / 1000UL);
    for (int i = 0; i < active_n_; i++) {
      Serial.print(F(","));
      Serial.print(y[i], 2);
    }
    Serial.println();

    if (settle_duration_ms_ >= 10000UL && elapsed_ms >= settle_duration_ms_ - 10000UL) {
      for (int i = 0; i < active_n_; i++) ybar_accumulator_[i] += y[i];
      ybar_sample_count_++;
    }

    if (elapsed_ms >= settle_duration_ms_) {
      for (int i = 0; i < active_n_; i++)
        ybar_[i] = (ybar_sample_count_ > 0) ? (ybar_accumulator_[i] / ybar_sample_count_) : y[i];
      Serial.print(F("EQ"));
      for (int i = 0; i < active_n_; i++) {
        Serial.print(F(","));
        Serial.print(ybar_[i], 3);
      }
      Serial.println();
      sample_index_ = 0;
      next_tick_ms_ = now;
      experiment_start_ms_ = now;
      state_ = EXPERIMENT;
    }
  }

  void tickExperiment(unsigned long now) {
    if ((long)(now - next_tick_ms_) < 0) return;

    float y[N];
    io_.readSensors(y, active_n_);
    if (safetyStop(y)) return;

    if (sample_index_ < T_) {
      float u_desired[M] = {0}, u_applied[M] = {0};
      for (int j = 0; j < active_m_; j++) {
        float input_deviation = rng_.uniform(-excitation_amplitude_, excitation_amplitude_);
        u_desired[j] = ubar_[j] + input_deviation;
      }
      io_.setActuators(u_desired, u_applied, active_m_);

      Serial.print(F("D,"));
      Serial.print(sample_index_);
      Serial.print(F(","));
      Serial.print(now - experiment_start_ms_);
      for (int i = 0; i < active_n_; i++) {
        Serial.print(F(","));
        Serial.print(y[i], 3);
      }
      for (int j = 0; j < active_m_; j++) {
        Serial.print(F(","));
        Serial.print(u_applied[j], 3);
      }
      Serial.println();
      sample_index_++;
      next_tick_ms_ += dt_ms_;
    } else {
      Serial.print(F("D,"));
      Serial.print(sample_index_);
      Serial.print(F(","));
      Serial.print(now - experiment_start_ms_);
      for (int i = 0; i < active_n_; i++) {
        Serial.print(F(","));
        Serial.print(y[i], 3);
      }
      for (int j = 0; j < active_m_; j++) Serial.print(F(",nan"));
      Serial.println();

      float u_applied[M] = {0};
      io_.setActuators(ubar_, u_applied, active_m_);  // segura o equilibrio enquanto o PC calcula
      state_ = WAITK;
      Serial.println(F("WAITK"));
    }
  }

  void tickControl(unsigned long now) {
    if ((long)(now - next_tick_ms_) < 0) return;

    float y[N];
    io_.readSensors(y, active_n_);
    if (safetyStop(y)) return;

    float u_desired[M] = {0};
    for (int i = 0; i < active_m_; i++) {
      float accumulated_input = ubar_[i];
      for (int j = 0; j < active_n_; j++) accumulated_input += K_[i][j] * (y[j] - setpoint_[j]);
      u_desired[i] = accumulated_input;
    }
    float u_applied[M] = {0};
    io_.setActuators(u_desired, u_applied, active_m_);

    unsigned long elapsed_ms = now - phase_start_ms_;
    Serial.print(F("C,"));
    Serial.print(elapsed_ms);  // ms inteiros, sem perda de precisao (era 1 casa decimal = 100ms)
    for (int i = 0; i < active_n_; i++) {
      Serial.print(F(","));
      Serial.print(y[i], 3);
    }
    for (int i = 0; i < active_m_; i++) {
      Serial.print(F(","));
      Serial.print(u_applied[i], 3);
    }
    Serial.println();
    next_tick_ms_ += dt_ms_;

    if (control_duration_ms_ > 0 && elapsed_ms >= control_duration_ms_) {
      io_.allOff();
      state_ = IDLE;
      Serial.println(F("END"));
    }
  }

  // Controle pautado pelo PC (lock-step nao-bloqueante). Fluxo por passo:
  //   firmware -> EC,<t_ms>,<y..>,<u_aplicado_anterior..>   (medida)
  //   PC       -> URAW,<u..>                                (comando cru)
  //   firmware aplica u, pauta a proxima medida dt depois (ver handleLine URAW)
  // A lei de controle vive no PC (Koopman racional / delay-embedding) -- o
  // firmware so mede, aplica e mede. Watchdog desliga tudo se o PC sumir.
  void tickExtControl(unsigned long now) {
    if (ext_awaiting_u_) {
      if ((now - ext_last_c_ms_) > EXT_WATCHDOG_MS) {
        io_.allOff();
        Serial.println(F("ERR,EXT_TIMEOUT"));
        state_ = IDLE;
      }
      return;  // ja mandou EC, esperando o URAW do PC
    }
    if ((long)(now - next_tick_ms_) < 0) return;

    float y[N];
    io_.readSensors(y, active_n_);
    if (safetyStop(y)) return;

    unsigned long elapsed_ms = now - phase_start_ms_;
    if (control_duration_ms_ > 0 && elapsed_ms >= control_duration_ms_) {
      io_.allOff();
      state_ = IDLE;
      Serial.println(F("END"));
      return;
    }

    Serial.print(F("EC,"));
    Serial.print(elapsed_ms);
    for (int i = 0; i < active_n_; i++) {
      Serial.print(F(","));
      Serial.print(y[i], 3);
    }
    for (int i = 0; i < active_m_; i++) {
      Serial.print(F(","));
      Serial.print(u_applied_prev_[i], 3);
    }
    Serial.println();
    ext_awaiting_u_ = true;
    ext_last_c_ms_ = now;
  }
};
