# -*- coding: utf-8 -*-
"""LMI data-driven (De Persis & Tesi, TAC 2020, Teorema 6) com margem rho.

    [ rho^2 (X0 Q)   X1 Q ]
    [ (X1 Q)'        X0 Q ]  > 0 ,   X0 Q > 0

    K = U0 Q (X0 Q)^-1   -- projetado SO com dados (nenhum modelo identificado).

rho e uma margem de decaimento (regiao-disco de raio rho no plano complexo),
uma generalizacao propria da eq. (15)/Teorema 3 do artigo -- NAO e o mesmo
"alpha" de robustez a ruido dos Teoremas 5/6 (formula diferente).

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
    G_K: np.ndarray      # (T, n) = Q (X0 Q)^-1, usado na verificacao de estabilidade
    status: str


def solve_gain(X0: np.ndarray, X1: np.ndarray, U0: np.ndarray, rho: float) -> GainResult:
    n, T = X0.shape
    Q = cp.Variable((T, n))
    X0_Q = X0 @ Q
    X1_Q = X1 @ Q

    lmi = cp.bmat([[rho**2 * X0_Q, X1_Q],
                   [X1_Q.T,        X0_Q]])
    constraints = [
        lmi >> 1e-6 * np.eye(2 * n),
        X0_Q >> 1e-6 * np.eye(n),
    ]
    problem = cp.Problem(cp.Minimize(0), constraints)
    try:
        problem.solve(solver=cp.CLARABEL)
    except Exception:
        problem.solve(solver=cp.SCS)

    if problem.status not in ("optimal", "optimal_inaccurate"):
        raise LMIInfeasibleError(
            f"LMI infactivel -- revise os dados/parametros (status={problem.status})."
        )

    Q_value = Q.value
    G_K = Q_value @ np.linalg.inv(X0 @ Q_value)
    K = U0 @ G_K
    return GainResult(K=K, G_K=G_K, status=problem.status)


def verify_stability(X1: np.ndarray, G_K: np.ndarray, rho: float) -> tuple[np.ndarray, bool, bool]:
    """Verificacao data-driven (sem A, B): Acl = X1 G_K."""
    closed_loop_eigenvalues = np.linalg.eigvals(X1 @ G_K)
    stable = bool(np.all(np.abs(closed_loop_eigenvalues) < 1.0))
    within_stability_margin = bool(np.all(np.abs(closed_loop_eigenvalues) < rho))
    return closed_loop_eigenvalues, stable, within_stability_margin
