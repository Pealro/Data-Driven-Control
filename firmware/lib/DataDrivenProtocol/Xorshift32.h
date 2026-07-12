/*
 * Xorshift32 -- PRNG determinístico minúsculo (Marsaglia), usado para gerar
 * a excitacao delta_u(k) DENTRO do microcontrolador, sem armazenar o vetor
 * inteiro em RAM. O PC so envia a semente (seed) e a amplitude via CFG; o
 * firmware recalcula delta_u(k) sob demanda, a cada passo do EXPERIMENT.
 *
 * Isso remove o unico array O(T) que o firmware chegou a ter (um buffer de
 * excitacao pre-calculada), entao a janela T deixa de ser limitada pela RAM
 * do Arduino.
 *
 * O PC nao precisa reproduzir esta sequencia -- o valor REALMENTE aplicado
 * (ja saturado) volta pelo protocolo em cada D,<k>,... e e isso que alimenta
 * X0/X1/U0, entao nao ha necessidade de bater bit-a-bit com nenhum RNG do
 * lado Python.
 */

#pragma once

#include <stdint.h>

class Xorshift32 {
public:
  Xorshift32() : state_(1) {}
  explicit Xorshift32(uint32_t seed) : state_(seed ? seed : 0x9E3779B9UL) {}

  uint32_t next() {
    uint32_t value = state_;
    value ^= value << 13;
    value ^= value >> 17;
    value ^= value << 5;
    state_ = value;
    return value;
  }

  // uniforme em [lower_bound, upper_bound)
  float uniform(float lower_bound, float upper_bound) {
    float normalized_random = (float)next() / 4294967295.0f;
    return lower_bound + (upper_bound - lower_bound) * normalized_random;
  }

private:
  uint32_t state_;
};
