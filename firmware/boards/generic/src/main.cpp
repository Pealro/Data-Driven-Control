/*
 * ===========================================================================
 *  firmware/boards/generic
 *  Controle data-driven (De Persis & Tesi, TAC 2020, Teorema 6) numa planta
 *  QUALQUER, ainda nao definida em codigo -- "nova planta definida pelo
 *  usuario" no wizard (runner.py). N_MAX=4 estados, M_MAX=4 entradas.
 *
 *  Grave este firmware UMA VEZ. O numero de canais realmente usados num
 *  experimento (n<=4, m<=4) vem do CFG (enviado pelo wizard), nao exige
 *  recompilar nem regravar -- so escolher, na hora, quantos canais usar.
 *
 *  Hardware (fixo nesta placa):
 *    Estados (Volts, AREF padrao 5V, SEM divisor de tensao):
 *      y1 = A0, y2 = A1, y3 = A2, y4 = A3
 *    Entradas (0..100% duty PWM -> 0..255):
 *      u1 = pino 3, u2 = pino 5, u3 = pino 6, u4 = pino 9
 *
 *  Sem leitura de retorno do PWM (ao contrario do rc_circuit): os 4 pinos
 *  analogicos disponiveis (A0-A3) ja sao usados para os estados -- A4/A5
 *  ficam livres caso queira adicionar isso manualmente depois.
 *
 *  Sem sensor especifico (TMP36 etc.): a leitura e sempre tensao pura em
 *  Volts. Se sua planta precisar de outra calibracao, converta no lado
 *  Python (datadriven/ nao assume unidade nenhuma).
 * ===========================================================================
 */

#include <Arduino.h>
#include <DataDrivenProtocol.h>

constexpr int N = 4;  // capacidade maxima de estados
constexpr int M = 4;  // capacidade maxima de entradas

const int PIN_Y[N] = {A0, A1, A2, A3};
const int PIN_U[M] = {3, 5, 6, 9};

const float AREF_V = 5.0;      // referencia padrao do Uno (sem AREF externo)
const float VOLTAGE_SAFE = 5.5;  // sanidade -- fisicamente inalcancavel com AREF=5V

float readVoltage(int pin) {
  long analog_read_accumulator = 0;
  for (int i = 0; i < 10; i++) analog_read_accumulator += analogRead(pin);
  return (analog_read_accumulator / 10.0) * AREF_V / 1024.0;
}

void readSensors(float y[N], int active_n) {
  for (int i = 0; i < active_n; i++) y[i] = readVoltage(PIN_Y[i]);
}

void setActuators(const float u_desired[M], float u_applied[M], int active_m) {
  for (int i = 0; i < active_m; i++) {
    float duty_percent = constrain(u_desired[i], 0.0, 100.0);
    analogWrite(PIN_U[i], (int)(duty_percent * 255.0 / 100.0 + 0.5));
    u_applied[i] = duty_percent;  // sem readback nesta placa -- ver nota no topo
  }
}

bool overSafetyLimit(const float y[N], int active_n) {
  for (int i = 0; i < active_n; i++)
    if (y[i] > VOLTAGE_SAFE) return true;
  return false;
}

void allOff() {
  for (int i = 0; i < M; i++) analogWrite(PIN_U[i], 0);
}

DataDrivenProtocol<N, M> protocol({readSensors, setActuators, overSafetyLimit, allOff});

void setup() {
  allOff();
  protocol.begin(115200);
}

void loop() { protocol.poll(); }
