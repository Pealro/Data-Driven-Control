# -*- coding: utf-8 -*-
"""EDMD bilinear: ajusta o modelo elevado z+ = A z + u(B0 + B1 z) + erro por
minimos quadrados (pinv). Y = [Z; U; Z*U] empilha regressor linear, de entrada e
bilinear; M = Z+ @ pinv(Y) e a matriz [A | B0 | B1]."""

import numpy as np


def build_bilinear_regressor(Z: np.ndarray, U: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Y = [Z; U; Z*U], mais o proprio Z*U (reaproveitado na predicao).
    Z (N,M), U (1,M) -> Y (2N+1, M)."""
    ZU = Z * U  # broadcasting (N,M)*(1,M) -> escala cada coluna z_k por u_k
    return np.vstack([Z, U, ZU]), ZU


def bilinear_edmd(Z0: np.ndarray, Z1: np.ndarray, U: np.ndarray) -> dict:
    """Ajusta A, B0, B1 tais que Z1 ~= A Z0 + B0 U + B1 (Z0*U).

    Z0, Z1 : (N, M) lifting no instante k e k+1
    U      : (1, M) entrada escalar (m=1)

    Retorna dict com A (N,N), B0 (N,1), B1 (N,N) e o erro relativo de predicao.
    """
    N = Z0.shape[0]
    Y, ZU = build_bilinear_regressor(Z0, U)
    M = Z1 @ np.linalg.pinv(Y)
    A = M[:, :N]
    B0 = M[:, N:N + 1]
    B1 = M[:, N + 1:2 * N + 1]

    Z1_pred = A @ Z0 + B0 @ U + B1 @ ZU
    erro = Z1 - Z1_pred
    norm_Z1 = np.linalg.norm(Z1, ord="fro")
    erro_rel = float(np.linalg.norm(erro, ord="fro") / norm_Z1) if norm_Z1 > 1e-14 else np.inf
    # erro so nas linhas de estado fisico (z[0:n_estado] = x); n_estado inferido
    # como o numero de linhas cujo expoente e de grau 1 nao e conhecido aqui, entao
    # deixamos o chamador cortar Z1[:n] se quiser -- aqui reportamos o global
    return {
        "A": A,
        "B0": B0,
        "B1": B1,
        "erro_rel": erro_rel,
        "cond_Y": float(np.linalg.cond(Y)),
    }
