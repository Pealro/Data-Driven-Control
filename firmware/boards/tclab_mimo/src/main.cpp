/*
 * ===========================================================================
 *  firmware/boards/tclab_mimo
 *  Controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6) no TCLab
 *  Planta MIMO: Q1,Q2 (aquecedores) -> T1,T2 (sensores). N=2, M=2.
 *
 *  ATENCAO: pinout padrao do TCLab (Q1=pino 3, Q2=pino 5, T1=A0, T2=A1),
 *  mas esta placa NAO FOI VALIDADA em hardware real neste projeto -- so o
 *  sketch SISO (firmware/boards/tclab_siso) foi testado ate agora. Confira
 *  calibracao (TMP36 x AREF) e T_SAFE antes de rodar experimentos.
 * ===========================================================================
 */

#include <Arduino.h>
#include <DataDrivenProtocol.h>

constexpr int N = 2;  // estados: T1, T2
constexpr int M = 2;  // entradas: Q1, Q2
// ------------------------- hardware (padrao TCLab) -------------------------
const int PIN_Q1 = 3;
const int PIN_Q2 = 5;
const int PIN_LED = 9;
const int PIN_T1 = A0;
const int PIN_T2 = A1;

#define USE_EXTERNAL_AREF 1
#if USE_EXTERNAL_AREF
const float MV_FULLSCALE = 3300.0;
#else
const float MV_FULLSCALE = 5000.0;
#endif

const float PMAX_Q = 200.0;  // potencia max. dos heaters (0..255), padrao TCLab
const float T_SAFE = 600.0;  // limite de seguranca [C] -> desliga tudo

float readTemp(int pin) {
  long analog_read_accumulator = 0;
  for (int i = 0; i < 10; i++) analog_read_accumulator += analogRead(pin);
  float millivolts = (analog_read_accumulator / 10.0) * MV_FULLSCALE / 1024.0;
  return (millivolts - 500.0) / 10.0;
}

void readSensors(float y[N], int active_n) {
  y[0] = readTemp(PIN_T1);
  y[1] = readTemp(PIN_T2);
}

void setActuators(const float u_desired[M], float u_applied[M], int active_m) {
  float duty_percent_q1 = constrain(u_desired[0], 0.0, 100.0);
  float duty_percent_q2 = constrain(u_desired[1], 0.0, 100.0);
  analogWrite(PIN_Q1, (int)(duty_percent_q1 * PMAX_Q / 100.0 + 0.5));
  analogWrite(PIN_Q2, (int)(duty_percent_q2 * PMAX_Q / 100.0 + 0.5));
  u_applied[0] = duty_percent_q1;
  u_applied[1] = duty_percent_q2;
}

bool overSafetyLimit(const float y[N], int active_n) { return y[0] > T_SAFE || y[1] > T_SAFE; }

void allOff() {
  analogWrite(PIN_Q1, 0);
  analogWrite(PIN_Q2, 0);
  digitalWrite(PIN_LED, LOW);
}

DataDrivenProtocol<N, M> protocol({readSensors, setActuators, overSafetyLimit, allOff});

void setup() {
  pinMode(PIN_LED, OUTPUT);
  allOff();
  protocol.begin(115200);
}

void loop() { protocol.poll(); }
