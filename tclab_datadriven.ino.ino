/*
 * ===========================================================================
 *  tclab_datadriven.ino
 *  Controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6) no TCLab
 *  Lado ARDUINO UNO R3  --  planta SISO: Q1 (aquecedor 1) -> T1 (sensor 1)
 *
 *  Este sketch substitui o firmware TCLab-sketch durante o experimento.
 *  Usa o MESMO pinout e a MESMA calibracao do firmware oficial do TCLab
 *  (aquecedor Q1 no pino 3, sensor TMP36 T1 em A0, AREF = 3.3 V).
 *  Para voltar a usar a lib python `tclab`, regrave o TCLab-sketch depois.
 *
 *  Fluxo (maquina de estados):
 *   IDLE -> (CFG + U,k,val ... + GO) -> SETTLE (assenta em ubar, mede Tbar)
 *        -> EXPERIMENT (aplica ubar+du(k), amostra T1, envia dados)
 *        -> WAITK (segura ubar, espera ganho do PC)
 *        -> (K,ganho,Tsp,ctrl_s) -> CONTROL (u = ubar + K*(T1-Tsp), streaming)
 *        -> END
 *
 *  Protocolo serial: 115200 baud, linhas ASCII terminadas em '\n'
 *   PC -> Arduino:
 *     CFG,<T>,<dt_ms>,<ubar>,<settle_s>   configuracao
 *     U,<k>,<du_k>                        k-esimo desvio de entrada [%]
 *     GO                                  inicia assentamento + experimento
 *     K,<ganho>,<Tsp>,<ctrl_s>            ganho (1x1), setpoint [C], duracao [s] (0=infinito)
 *     X                                   aborta (desliga aquecedores)
 *   Arduino -> PC:
 *     ACK,CFG | ACK,U,<k> | ACK,GO | ACK,K
 *     S,<t_s>,<T1>                        streaming do assentamento (1 Hz)
 *     EQ,<Tbar>                           equilibrio medido
 *     D,<k>,<T1>,<u_aplicado>             amostra do experimento (u='nan' no ultimo)
 *     WAITK                               dados enviados, aguardando K
 *     C,<t_s>,<T1>,<u>                    streaming do controle em tempo real
 *     END | ERR,<msg>
 * ===========================================================================
 */

#include <Arduino.h>

// ------------------------- hardware (padrao TCLab) -------------------------
const int PIN_Q1  = 3;    // aquecedor 1 (PWM)
const int PIN_Q2  = 5;    // aquecedor 2 (mantido em 0 neste projeto)
const int PIN_LED = 9;    // LED do shield
const int PIN_T1  = A0;   // sensor de temperatura 1 (TMP36)

// Shield TCLab liga 3.3 V ao pino AREF -> usar referencia EXTERNA (3300 mV).
// Se estiver SEM o shield/AREF, mude para 0 (usa 5000 mV, referencia DEFAULT).
#define USE_EXTERNAL_AREF 1
#if USE_EXTERNAL_AREF
  const float MV_FULLSCALE = 3300.0;
#else
  const float MV_FULLSCALE = 5000.0;
#endif

const float PMAX_Q1 = 200.0;   // potencia max. do heater 1 (0..255), padrao TCLab
const float T_SAFE  = 600.0;    // limite de seguranca [C] -> desliga tudo
const int   T_CAP   = 120;     // tamanho maximo do vetor de entrada (RAM do Uno)

// ------------------------- estado do protocolo -----------------------------
enum State { IDLE, READY, SETTLE, EXPERIMENT, WAITK, CONTROL };
State state = IDLE;

int           Tlen      = 0;      // janela T
unsigned long dt_ms     = 4000;   // taxa de amostragem [ms]
float         ubar      = 0.0;    // entrada de equilibrio [%]
unsigned long settle_ms = 0;      // tempo de assentamento [ms]
float         du[T_CAP];          // vetor de desvios de entrada [%]
int           nrec      = 0;      // quantos U ja recebidos

float         Kgain   = 0.0;      // ganho K (1x1) -- delta_u = K * delta_x
float         Tsp     = 0.0;      // setpoint de temperatura [C]
unsigned long ctrl_ms = 0;        // duracao do controle (0 = infinito)

unsigned long t0 = 0, nextTick = 0, lastSettleMsg = 0;
int   kstep   = 0;
float TbarAcc = 0.0;
int   TbarN   = 0;
float Tbar    = 0.0;

char buf[64];
byte blen = 0;

// ------------------------- utilidades ------------------------------------
float readT1() {
  // media de 10 leituras, calibracao TMP36: T[C] = (mV - 500)/10
  long acc = 0;
  for (int i = 0; i < 10; i++) acc += analogRead(PIN_T1);
  float mV = (acc / 10.0) * MV_FULLSCALE / 1024.0;
  return (mV - 500.0) / 10.0;
}

void setQ1(float pct) {
  pct = constrain(pct, 0.0, 100.0);
  analogWrite(PIN_Q1, (int)(pct * PMAX_Q1 / 100.0 + 0.5));
}

void allOff() {
  analogWrite(PIN_Q1, 0);
  analogWrite(PIN_Q2, 0);
  digitalWrite(PIN_LED, LOW);
}

bool overTemp(float T1) {
  if (T1 > T_SAFE) {
    allOff();
    Serial.print(F("ERR,OVERTEMP,")); Serial.println(T1, 2);
    state = IDLE;
    return true;
  }
  return false;
}

// ------------------------- parser de comandos -----------------------------
void handleLine(char *line) {
  char *tok = strtok(line, ",");
  if (tok == NULL) return;

  if (strcmp(tok, "X") == 0) {                    // aborta a qualquer momento
    allOff();
    state = IDLE;
    Serial.println(F("END"));
    return;
  }

  if (strcmp(tok, "CFG") == 0) {
    Tlen      = atoi(strtok(NULL, ","));
    dt_ms     = (unsigned long)atol(strtok(NULL, ","));
    ubar      = atof(strtok(NULL, ","));
    settle_ms = (unsigned long)atol(strtok(NULL, ",")) * 1000UL;
    if (Tlen <= 0 || Tlen > T_CAP) { Serial.println(F("ERR,T_INVALIDO")); return; }
    nrec  = 0;
    state = READY;
    Serial.println(F("ACK,CFG"));
    return;
  }

  if (strcmp(tok, "U") == 0 && state == READY) {
    int   k = atoi(strtok(NULL, ","));
    float v = atof(strtok(NULL, ","));
    if (k >= 0 && k < Tlen) {
      du[k] = v;
      nrec++;
      Serial.print(F("ACK,U,")); Serial.println(k);
    }
    return;
  }

  if (strcmp(tok, "GO") == 0 && state == READY) {
    if (nrec < Tlen) { Serial.println(F("ERR,VETOR_INCOMPLETO")); return; }
    digitalWrite(PIN_LED, HIGH);
    setQ1(ubar);                      // comeca o assentamento
    analogWrite(PIN_Q2, 0);
    t0 = millis();
    lastSettleMsg = 0;
    TbarAcc = 0.0; TbarN = 0;
    state = SETTLE;
    Serial.println(F("ACK,GO"));
    return;
  }

  if (strcmp(tok, "K") == 0 && state == WAITK) {
    Kgain   = atof(strtok(NULL, ","));
    Tsp     = atof(strtok(NULL, ","));
    ctrl_ms = (unsigned long)atol(strtok(NULL, ",")) * 1000UL;
    t0 = millis();
    nextTick = t0;
    state = CONTROL;
    Serial.println(F("ACK,K"));
    return;
  }
}

// ------------------------- setup / loop -----------------------------------
void setup() {
//#if USE_EXTERNAL_AREF
//  analogReference(EXTERNAL);
//#endif
  pinMode(PIN_LED, OUTPUT);
  allOff();
  Serial.begin(115200);
  Serial.println(F("TCLAB-DD,READY"));   // banner de boot
}

void loop() {
  // ---- leitura serial nao bloqueante ----
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (blen > 0) { buf[blen] = '\0'; handleLine(buf); blen = 0; }
    } else if (blen < sizeof(buf) - 1) {
      buf[blen++] = c;
    }
  }

  unsigned long now = millis();

  // ---- fase de assentamento no equilibrio (ubar) ----
  if (state == SETTLE) {
    if (now - lastSettleMsg >= 1000UL) {
      lastSettleMsg = now;
      float T1 = readT1();
      if (overTemp(T1)) return;
      unsigned long el = now - t0;
      Serial.print(F("S,")); Serial.print(el / 1000UL);
      Serial.print(F(","));  Serial.println(T1, 2);
      // media dos ultimos 10 s do assentamento -> Tbar
      if (settle_ms >= 10000UL && el >= settle_ms - 10000UL) {
        TbarAcc += T1; TbarN++;
      }
      if (el >= settle_ms) {
        Tbar = (TbarN > 0) ? (TbarAcc / TbarN) : T1;
        Serial.print(F("EQ,")); Serial.println(Tbar, 3);
        kstep = 0;
        nextTick = now;
        state = EXPERIMENT;
      }
    }
  }

  // ---- experimento de coleta de dados ----
  // ordem por passo k: le x(k), aplica u(k)=ubar+du(k), transmite.
  // no passo final (k=T) le apenas x(T) e mantem ubar.
  else if (state == EXPERIMENT) {
    if ((long)(now - nextTick) >= 0) {
      float T1 = readT1();
      if (overTemp(T1)) return;
      if (kstep < Tlen) {
        float u = constrain(ubar + du[kstep], 0.0, 100.0);
        setQ1(u);
        Serial.print(F("D,")); Serial.print(kstep);
        Serial.print(F(","));  Serial.print(T1, 3);
        Serial.print(F(","));  Serial.println(u, 3);
        kstep++;
        nextTick += dt_ms;
      } else {
        Serial.print(F("D,")); Serial.print(kstep);
        Serial.print(F(","));  Serial.print(T1, 3);
        Serial.println(F(",nan"));
        setQ1(ubar);                 // segura o equilibrio enquanto o PC calcula
        state = WAITK;
        Serial.println(F("WAITK"));
      }
    }
  }

  // ---- controle em malha fechada, streaming em tempo real ----
  // lei de controle: u = ubar + K * (T1 - Tsp)   [delta_u = K * delta_x]
  else if (state == CONTROL) {
    if ((long)(now - nextTick) >= 0) {
      float T1 = readT1();
      if (overTemp(T1)) return;
      float u = constrain(ubar + Kgain * (T1 - Tsp), 0.0, 100.0);
      setQ1(u);
      unsigned long el = now - t0;
      Serial.print(F("C,")); Serial.print(el / 1000.0, 1);
      Serial.print(F(","));  Serial.print(T1, 3);
      Serial.print(F(","));  Serial.println(u, 3);
      nextTick += dt_ms;
      if (ctrl_ms > 0 && el >= ctrl_ms) {
        allOff();
        state = IDLE;
        Serial.println(F("END"));
      }
    }
  }
}
