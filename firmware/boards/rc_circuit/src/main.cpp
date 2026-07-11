/*
 * ===========================================================================
 *  firmware/boards/rc_circuit
 *  Controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6) num circuito
 *  RC simples: pino 3 = sinal/alimentacao PWM (entrada), A0 = leitura de
 *  tensao no capacitor (estado). N=1, M=1.
 *
 *  Diferente da TCLab: nao ha sensor TMP36 (leitura e tensao pura, nao
 *  temperatura) e nao ha risco termico -- o limite de seguranca aqui e so
 *  uma checagem de sanidade contra erro de fiacao.
 *
 *  Hardware:
 *    PIN_IN  (pino 3, PWM)  -> sinal de entrada do RC (0..100% duty -> 0..255)
 *    PIN_OUT (A0)           -> leitura de tensao no capacitor, AREF padrao
 *                              (5V), SEM divisor de tensao (V = raw/1024*5V)
 * ===========================================================================
 */

#include <Arduino.h>
#include <DataDrivenProtocol.h>

constexpr int N = 1;  // estado: tensao no capacitor
constexpr int M = 1;  // entrada: duty PWM do sinal de excitacao
constexpr int T_CAP = 200;

const int PIN_IN = 3;    // sinal/alimentacao da planta (PWM)
const int PIN_OUT = A0;  // leitura de tensao

const float AREF_V = 5.0;       // referencia padrao do Uno (sem AREF externo)
const float V_SAFE = 5.5;       // sanidade -- fisicamente inalcancavel com AREF=5V,
                                 // mantido caso a fiacao mude no futuro

float readVoltage() {
  long acc = 0;
  for (int i = 0; i < 10; i++) acc += analogRead(PIN_OUT);
  return (acc / 10.0) * AREF_V / 1024.0;
}

void readSensors(float y[N]) { y[0] = readVoltage(); }

void setActuators(const float uDesired[M], float uApplied[M]) {
  float pct = constrain(uDesired[0], 0.0, 100.0);
  analogWrite(PIN_IN, (int)(pct * 255.0 / 100.0 + 0.5));
  uApplied[0] = pct;
}

bool overSafetyLimit(const float y[N]) { return y[0] > V_SAFE; }

void allOff() { analogWrite(PIN_IN, 0); }

DataDrivenProtocol<N, M, T_CAP> dd({readSensors, setActuators, overSafetyLimit, allOff});

void setup() {
  allOff();
  dd.begin(115200);
}

void loop() { dd.poll(); }
