# -*- coding: utf-8 -*-
"""Geracao do sinal de excitacao persistente (Assumption 5)."""

import numpy as np


def generate_excitation(T: int, m: int, amp: float, seed: int | None = None) -> np.ndarray:
    """Gera du(k) ~ U(-amp, +amp), k = 0..T-1.

    Retorna array (m, T) com o desvio de entrada a aplicar em cada canal.
    """
    rng = np.random.default_rng(seed)
    return rng.uniform(-amp, amp, size=(m, T))
