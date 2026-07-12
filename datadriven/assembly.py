# -*- coding: utf-8 -*-
"""Montagem de X0, X1, U0 (desvios em torno do equilibrio) a partir dos
dados brutos coletados na planta. Agnostico de n (estados) e m (entradas)."""

import numpy as np


def build_X0_X1_U0(
    y_raw: np.ndarray,
    u_raw: np.ndarray,
    ybar: np.ndarray,
    ubar: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    y_raw : (n, T+1) leituras absolutas de estado, incluindo o equilibrio -- y(0)..y(T)
    u_raw : (m, T)   entrada REALMENTE aplicada (ja com saturacao) -- u(0)..u(T-1)
    ybar  : (n,)     estado de equilibrio medido
    ubar  : (m,)     entrada de equilibrio

    Retorna X0 (n,T), X1 (n,T), U0 (m,T) -- notacao de X_{0,T}, X_{1,T},
    U_{0,1,T} do artigo (De Persis & Tesi, 2020, eq. 51, Teorema 6).
    """
    n, sample_count = y_raw.shape  # sample_count = T + 1 (inclui o estado inicial)
    T = sample_count - 1
    state_deviation = y_raw - ybar.reshape(n, 1)
    X0 = state_deviation[:, 0:T]
    X1 = state_deviation[:, 1:T + 1]
    U0 = u_raw - ubar.reshape(-1, 1)
    return X0, X1, U0
