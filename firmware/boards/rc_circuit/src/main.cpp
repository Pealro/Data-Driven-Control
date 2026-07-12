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
 *    PIN_IN               (pino 3, PWM) -> sinal de entrada do RC (0..100% duty -> 0..255)
 *    PIN_OUT               (A0)         -> leitura de tensao no capacitor (estado), AREF padrao
 *                                          (5V), SEM divisor de tensao (V = raw/1024*5V)
 *    PIN_ACTUATOR_READBACK (A5)         -> leitura da propria saida PWM do pino 3 (ligacao
 *                                          direta A5<-pino3): mede o duty REALMENTE presente
 *                                          no pino, em vez de reportar de volta o valor que
 *                                          apenas calculamos e mandamos aplicar.
 * ===========================================================================
 */

#include <Arduino.h>
#include <DataDrivenProtocol.h>

constexpr int N = 1;  // estado: tensao no capacitor
constexpr int M = 1;  // entrada: duty PWM do sinal de excitacao

const int PIN_IN = 3;                  // sinal/alimentacao da planta (PWM)
const int PIN_OUT = A0;                // leitura de tensao (estado)
const int PIN_ACTUATOR_READBACK = A5;  // leitura real do duty aplicado no pino 3

const float AREF_V = 5.0;       // referencia padrao do Uno (sem AREF externo)
const float V_SAFE = 5.5;       // sanidade -- fisicamente inalcancavel com AREF=5V,
                                 // mantido caso a fiacao mude no futuro

float readVoltage(int pin) {
  long analog_read_accumulator = 0;
  for (int i = 0; i < 10; i++) analog_read_accumulator += analogRead(pin);
  return (analog_read_accumulator / 10.0) * AREF_V / 1024.0;
}

void readSensors(float y[N]) { y[0] = readVoltage(PIN_OUT); }

void setActuators(const float u_desired[M], float u_applied[M]) {
  float duty_percent = constrain(u_desired[0], 0.0, 100.0);
  analogWrite(PIN_IN, (int)(duty_percent * 255.0 / 100.0 + 0.5));

  // le de volta o duty REALMENTE presente no pino (media de 10 amostras,
  // igual ao estado) em vez de ecoar o valor calculado -- fecha a malha
  // de verificacao: o que o Arduino diz que aplicou e o que o pino mostra.
  float measured_voltage = readVoltage(PIN_ACTUATOR_READBACK);
  u_applied[0] = (measured_voltage / AREF_V) * 100.0;
}

bool overSafetyLimit(const float y[N]) { return y[0] > V_SAFE; }

void allOff() { analogWrite(PIN_IN, 0); }

DataDrivenProtocol<N, M> protocol({readSensors, setActuators, overSafetyLimit, allOff});

void setup() {
  allOff();
  protocol.begin(115200);
}

void loop() { protocol.poll(); }
