# -*- coding: utf-8 -*-
"""Geracao do sinal de excitacao persistente (Assumption 5)."""

import numpy as np


def generate_excitation(
    T: int, m: int, excitation_amplitude: float, seed: int | None = None
) -> np.ndarray:
    """Gera a excitacao persistente delta_u(k) ~ U(-excitation_amplitude,
    +excitation_amplitude), k = 0..T-1 (corresponde a delta_u_d do Teorema 6
    de De Persis & Tesi, 2020).

    Retorna input_deviation (m, T): o desvio de entrada a aplicar em cada canal.
    """
    rng = np.random.default_rng(seed)
    input_deviation = rng.uniform(-excitation_amplitude, excitation_amplitude, size=(m, T))
    return input_deviation
