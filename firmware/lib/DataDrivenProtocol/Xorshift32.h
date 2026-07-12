/*
 * Xorshift32 -- PRNG determinístico minúsculo (Marsaglia), usado para gerar
 * a excitacao du(k) DENTRO do microcontrolador, sem armazenar o vetor
 * inteiro em RAM. O PC so envia a semente (seed) e a amplitude via CFG; o
 * firmware recalcula du(k) sob demanda, a cada passo do EXPERIMENT.
 *
 * Isso remove o unico array O(T) do firmware (o antigo du_[M][T_CAP]),
 * entao a janela T deixa de ser limitada pela RAM do Arduino.
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
    uint32_t x = state_;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    state_ = x;
    return x;
  }

  // uniforme em [lo, hi)
  float uniform(float lo, float hi) {
    float u01 = (float)next() / 4294967295.0f;
    return lo + (hi - lo) * u01;
  }

private:
  uint32_t state_;
};
