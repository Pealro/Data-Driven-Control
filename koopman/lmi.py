# -*- coding: utf-8 -*-
"""LMI robusta de Koopman (Strasser et al. 2023, Teorema 4 -- caso NOMINAL,
entrada escalar m=1). Projeta o controlador racional u = (Kz)/(1-Kw z) que
estabiliza o sistema bilinear elevado z+ = A z + u(B0 + B1 z).

Fiel a solve_lmi_autores_m1_nominal do notebook. Unica diferenca: o solver nao e
mais preso a uma licenca MOSEK de outra maquina -- make_solver() escolhe o
melhor disponivel (MOSEK e o unico que resolve estas LMIs na pratica; CLARABEL/
SCS raramente convergem, mas ficam como fallback com aviso)."""

import cvxpy as cp
import numpy as np

from datadriven.solver_util import solve_lmi


def make_solver(preferencia=("MOSEK", "CLARABEL", "SCS")) -> str:
    disponiveis = cp.installed_solvers()
    for s in preferencia:
        if s in disponiveis:
            return s
    return disponiveis[0]


def simetrizar(M) -> np.ndarray:
    M = np.asarray(M, dtype=float)
    return 0.5 * (M + M.T)


def _cond_posdef(M) -> float:
    eigs = np.linalg.eigvalsh(simetrizar(M))
    return float(np.max(eigs) / np.min(eigs))


def solve_koopman_lmi(
    A, B0, B1, Rz,
    eps_P=1e-9, eps_Lambda=1e-9, eps_nu=1e-9, eps_F=1e-9,
    solver=None, verbose=False, log_path=None,
) -> dict:
    """Resolve a LMI nominal (m=1) com Qz=-I, Sz=0, Rz escalar, cx=cu=0.
    Retorna dict com sucesso, K (1,N), Kw (1,N), P, Pinv, lambda, nu e diagnostico.

    O solver segue o padrao do projeto (MOSEK verbose -> SCS, ver abaixo); os
    parametros solver/verbose sao aceitos por compatibilidade mas ignorados."""
    A = np.asarray(A, dtype=float)
    B0 = np.asarray(B0, dtype=float).reshape(A.shape[0], 1)
    B1 = np.asarray(B1, dtype=float)
    N_lift = A.shape[0]
    I_N = np.eye(N_lift)
    tRz = 1.0 / float(Rz)

    P = cp.Variable((N_lift, N_lift), symmetric=True)
    L = cp.Variable((1, N_lift))
    Lw = cp.Variable((1, N_lift))
    lam = cp.Variable(nonneg=True)
    nu = cp.Variable(nonneg=True)
    constraints = [P >> eps_P * I_N, lam >= eps_Lambda, nu >= eps_nu]

    F11 = P
    F12 = np.zeros((N_lift, 1))
    F14 = A @ P + B0 @ L
    F15 = B1 * lam + B0 @ Lw
    F22 = (lam * tRz) * np.ones((1, 1))
    F24 = L
    F25 = Lw
    F44 = P
    F45 = np.zeros((N_lift, N_lift))
    F55 = lam * I_N
    F = cp.bmat([
        [F11, F12, F14, F15],
        [F12.T, F22, F24, F25],
        [F14.T, F24.T, F44, F45],
        [F15.T, F25.T, F45.T, F55],
    ])
    F = 0.5 * (F + F.T)
    constraints.append(F >> eps_F * np.eye(3 * N_lift + 1))

    # FI <= 0: com Qz=-I, Sz=0 vira diag(nu/Rz - 1, P - nu I)
    FI11 = (nu * tRz - 1.0) * np.ones((1, 1))
    FI12 = np.zeros((1, N_lift))
    FI22 = P - nu * I_N
    FI = cp.bmat([[FI11, FI12], [FI12.T, FI22]])
    FI = 0.5 * (FI + FI.T)
    constraints.append(FI << 0)

    problem = cp.Problem(cp.Maximize(cp.trace(P)), constraints)
    # padrao do projeto: MOSEK (verbose->log_path) primeiro, CLARABEL de fallback
    # (nao SCS -- ver datadriven/solver_util.py). O try externo mantem o retorno
    # sucesso=False se AMBOS falharem, para a busca em grade continuar.
    try:
        solve_lmi(problem, log_path=log_path)
    except Exception as erro:
        return {"sucesso": False, "status": "erro_solver", "erro": str(erro), "Rz": float(Rz)}
    if problem.status not in ("optimal", "optimal_inaccurate"):
        return {"sucesso": False, "status": problem.status, "erro": None, "Rz": float(Rz)}

    P_val = simetrizar(P.value)
    L_val = np.asarray(L.value, dtype=float)
    Lw_val = np.asarray(Lw.value, dtype=float)
    lam_val = float(lam.value)
    Pinv_val = simetrizar(np.linalg.solve(P_val, I_N))
    return {
        "sucesso": True,
        "status": problem.status,
        "erro": None,
        "Rz": float(Rz),
        "eps_F": float(eps_F),
        "P": P_val,
        "Pinv": Pinv_val,
        "K": L_val @ Pinv_val,
        "Kw": Lw_val / lam_val,
        "lambda": lam_val,
        "nu": float(nu.value),
        "traceP": float(np.trace(P_val)),
        "condP": _cond_posdef(P_val),
    }
