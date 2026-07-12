/*
 * ===========================================================================
 *  firmware/boards/tclab_siso
 *  Controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6) no TCLab
 *  Planta SISO: Q1 (aquecedor 1) -> T1 (sensor 1). N=1, M=1.
 *
 *  Mesmo pinout e mesma calibracao do sketch legado tclab_datadriven.ino.ino
 *  (aquecedor Q1 no pino 3, sensor TMP36 T1 em A0, AREF = 3.3 V via shield
 *  TCLab). A maquina de estados e o parser do protocolo vivem em
 *  firmware/lib/DataDrivenProtocol -- este arquivo so implementa os hooks
 *  de hardware (PlantIO).
 *
 *  Para voltar a usar a lib python `tclab`, regrave o firmware original.
 * ===========================================================================
 */

#include <Arduino.h>
#include <DataDrivenProtocol.h>

constexpr int N = 1;  // estados: T1
constexpr int M = 1;  // entradas: Q1

// ------------------------- hardware (padrao TCLab) -------------------------
const int PIN_Q1 = 3;   // aquecedor 1 (PWM)
const int PIN_Q2 = 5;   // aquecedor 2 (mantido em 0 neste projeto)
const int PIN_LED = 9;  // LED do shield
const int PIN_T1 = A0;  // sensor de temperatura 1 (TMP36)

// Shield TCLab liga 3.3 V ao pino AREF -> em teoria deveria usar referencia
// EXTERNA (3300 mV). O sketch legado NAO chama analogReference(EXTERNAL)
// (fica comentado abaixo) -- mantido identico ao firmware que gerou os dados
// ja coletados (dados_experimento.csv). Nao altere sem revalidar a calibracao.
#define USE_EXTERNAL_AREF 1
#if USE_EXTERNAL_AREF
const float MV_FULLSCALE = 3300.0;
#else
const float MV_FULLSCALE = 5000.0;
#endif

const float PMAX_Q1 = 200.0;  // potencia max. do heater 1 (0..255), padrao TCLab
const float T_SAFE = 600.0;   // limite de seguranca [C] -> desliga tudo

float readT1() {
  long acc = 0;
  for (int i = 0; i < 10; i++) acc += analogRead(PIN_T1);
  float mV = (acc / 10.0) * MV_FULLSCALE / 1024.0;
  return (mV - 500.0) / 10.0;
}

void readSensors(float y[N]) { y[0] = readT1(); }

void setActuators(const float uDesired[M], float uApplied[M]) {
  float pct = constrain(uDesired[0], 0.0, 100.0);
  analogWrite(PIN_Q1, (int)(pct * PMAX_Q1 / 100.0 + 0.5));
  uApplied[0] = pct;
}

bool overSafetyLimit(const float y[N]) { return y[0] > T_SAFE; }

void allOff() {
  analogWrite(PIN_Q1, 0);
  analogWrite(PIN_Q2, 0);
  digitalWrite(PIN_LED, LOW);
}

DataDrivenProtocol<N, M> dd({readSensors, setActuators, overSafetyLimit, allOff});

void setup() {
  //#if USE_EXTERNAL_AREF
  //  analogReference(EXTERNAL);
  //#endif
  pinMode(PIN_LED, OUTPUT);
  allOff();
  dd.begin(115200);
}

void loop() { dd.poll(); }
