# -*- coding: utf-8 -*-
"""Diagnosticos de qualidade dos dados coletados -- persistencia de
excitacao, residuo estimado (proxy da Assumption 5), saturacao e excursao."""

import numpy as np


def check_persistency_of_excitation(U0: np.ndarray, X0: np.ndarray, n: int, m: int) -> tuple[int, bool]:
    """rank([U0; X0]) == n + m e condicao necessaria para a LMI ser factivel."""
    rank = int(np.linalg.matrix_rank(np.vstack([U0, X0])))
    return rank, rank == n + m


def estimate_residual_gamma(X0: np.ndarray, X1: np.ndarray, U0: np.ndarray) -> float:
    """Estimativa de gamma (proxy da Assumption 5) via residuo do melhor
    ajuste linear (Teorema 1). Apenas diagnostico -- K continua 100% data-driven."""
    S = np.vstack([U0, X0])
    BA_hat = X1 @ np.linalg.pinv(S)
    D0_hat = X1 - BA_hat @ S
    num = np.max(np.linalg.eigvals(D0_hat @ D0_hat.T).real)
    den = np.min(np.linalg.eigvals(X1 @ X1.T).real)
    return float(num / den)


def check_saturation(u_raw: np.ndarray, u_min: float | None = None, u_max: float | None = None) -> int:
    """Numero de amostras de entrada que saturaram nos limites do atuador.

    u_min/u_max sao os limites REAIS do atuador da planta (ex.: TCLab = 0..100%).
    None desativa o respectivo lado do teste -- plantas sem saturacao conhecida
    (ex.: simulada generica) nao devem ser marcadas como "saturadas" por um
    limite que nao existe.
    """
    if u_min is None and u_max is None:
        return 0
    lo = -np.inf if u_min is None else u_min
    hi = np.inf if u_max is None else u_max
    return int(np.sum((u_raw <= lo) | (u_raw >= hi)))


def check_excursion(X0: np.ndarray, X1: np.ndarray, amp_estado: float) -> tuple[float, bool]:
    """Excursao maxima do estado; True se excedeu o limite esperado (amp_estado)."""
    exc_max = float(np.max(np.abs(np.hstack([X0, X1]))))
    return exc_max, exc_max > amp_estado


def check_sampling_rate(
    t_raw: np.ndarray, dt: float, tol: float = 0.2
) -> tuple[float, bool]:
    """Compara o dt REAL medido (t_raw, ex.: via millis() no microcontrolador)
    com o dt configurado. Se o passo de processamento (leitura + envio serial)
    demorar mais que dt, o laco fica limitado pelo tempo de execucao e o dt
    real sera maior que o pedido -- isso enviesa a identificacao (X0/X1 nao
    correspondem ao dt que voce pensa que usou).

    Retorna (dt_medido, excedeu_tolerancia). tol e a fracao de desvio
    aceitavel (0.2 = 20%).
    """
    dt_medido = float(np.mean(np.diff(t_raw)))
    excedeu = abs(dt_medido - dt) > tol * dt
    return dt_medido, excedeu
