# -*- coding: utf-8 -*-
"""LMI data-driven (De Persis & Tesi, TAC 2020, Teorema 6) com margem rho.

    [ rho^2 (X0 Q)   X1 Q ]
    [ (X1 Q)'        X0 Q ]  > 0 ,   X0 Q > 0

    K = U0 Q (X0 Q)^-1   -- projetado SO com dados (nenhum modelo identificado).

Generaliza para n estados e m entradas: Q e (T,n), K sai (m,n).
"""

from dataclasses import dataclass

import cvxpy as cp
import numpy as np


class LMIInfeasibleError(RuntimeError):
    pass


@dataclass
class GainResult:
    K: np.ndarray       # (m, n) ganho data-driven
    GK: np.ndarray      # (T, n) = Q (X0 Q)^-1, usado na verificacao de estabilidade
    status: str


def solve_gain(X0: np.ndarray, X1: np.ndarray, U0: np.ndarray, rho: float) -> GainResult:
    n, T = X0.shape
    Q = cp.Variable((T, n))
    X0Q = X0 @ Q
    X1Q = X1 @ Q

    lmi = cp.bmat([[rho**2 * X0Q, X1Q],
                   [X1Q.T,        X0Q]])
    constraints = [
        lmi >> 1e-6 * np.eye(2 * n),
        X0Q >> 1e-6 * np.eye(n),
    ]
    prob = cp.Problem(cp.Minimize(0), constraints)
    try:
        prob.solve(solver=cp.CLARABEL)
    except Exception:
        prob.solve(solver=cp.SCS)

    if prob.status not in ("optimal", "optimal_inaccurate"):
        raise LMIInfeasibleError(f"LMI infactivel -- revise os dados/parametros (status={prob.status}).")

    Qv = Q.value
    GK = Qv @ np.linalg.inv(X0 @ Qv)
    K = U0 @ GK
    return GainResult(K=K, GK=GK, status=prob.status)


def verify_stability(X1: np.ndarray, GK: np.ndarray, rho: float) -> tuple[np.ndarray, bool, bool]:
    """Verificacao data-driven (sem A, B): Acl = X1 GK."""
    eig = np.linalg.eigvals(X1 @ GK)
    stable = bool(np.all(np.abs(eig) < 1.0))
    within_margin = bool(np.all(np.abs(eig) < rho))
    return eig, stable, within_margin
