# -*- coding: utf-8 -*-
"""Diagnosticos de qualidade dos dados coletados -- persistencia de
excitacao, residuo estimado (proxy da Assumption 5), saturacao e excursao."""

import numpy as np


def check_persistency_of_excitation(
    U0: np.ndarray, X0: np.ndarray, n: int, m: int
) -> tuple[int, bool]:
    """rank([U0; X0]) == n + m e condicao necessaria para a LMI ser factivel
    (condicao (6) de De Persis & Tesi, 2020)."""
    rank = int(np.linalg.matrix_rank(np.vstack([U0, X0])))
    is_persistently_exciting = rank == n + m
    return rank, is_persistently_exciting


def estimate_residual_gamma(X0: np.ndarray, X1: np.ndarray, U0: np.ndarray) -> float:
    """Estimativa de gamma (proxy da Assumption 5: D0_hat @ D0_hat.T <=
    gamma * X1 @ X1.T) via residuo do melhor ajuste linear [B A] (Teorema 1).
    Apenas diagnostico -- K continua 100% data-driven."""
    stacked_input_state = np.vstack([U0, X0])
    BA_hat = X1 @ np.linalg.pinv(stacked_input_state)
    D0_hat = X1 - BA_hat @ stacked_input_state
    # eigvalsh (nao eigvals): as matrizes de Gram sao simetricas PSD por
    # construcao -- solver simetrico e mais rapido, estavel, e ja retorna
    # autovalores reais em ordem crescente
    max_residual_eigenvalue = np.linalg.eigvalsh(D0_hat @ D0_hat.T)[-1]
    min_signal_eigenvalue = np.linalg.eigvalsh(X1 @ X1.T)[0]
    return float(max_residual_eigenvalue / min_signal_eigenvalue)


def check_saturation(
    u_raw: np.ndarray, u_min: float | None = None, u_max: float | None = None
) -> int:
    """Numero de amostras de entrada que saturaram nos limites do atuador.

    u_min/u_max sao os limites REAIS do atuador da planta (ex.: TCLab = 0..100%).
    None desativa o respectivo lado do teste -- plantas sem saturacao conhecida
    (ex.: simulada generica) nao devem ser marcadas como "saturadas" por um
    limite que nao existe.
    """
    if u_min is None and u_max is None:
        return 0
    lower_bound = -np.inf if u_min is None else u_min
    upper_bound = np.inf if u_max is None else u_max
    return int(np.sum((u_raw <= lower_bound) | (u_raw >= upper_bound)))


def check_excursion(
    X0: np.ndarray, X1: np.ndarray, max_expected_state_deviation: float
) -> tuple[float, bool]:
    """Excursao maxima do estado; True se excedeu o limite esperado
    (max_expected_state_deviation)."""
    max_state_deviation = float(np.max(np.abs(np.hstack([X0, X1]))))
    exceeded_expected_deviation = max_state_deviation > max_expected_state_deviation
    return max_state_deviation, exceeded_expected_deviation


def check_sampling_rate(
    t_raw: np.ndarray, dt: float, tolerance_fraction: float = 0.2
) -> tuple[float, bool]:
    """Compara o dt REAL medido (t_raw, ex.: via millis() no microcontrolador)
    com o dt configurado. Se o passo de processamento (leitura + envio serial)
    demorar mais que dt, o laco fica limitado pelo tempo de execucao e o dt
    real sera maior que o pedido -- isso enviesa a identificacao (X0/X1 nao
    correspondem ao dt que voce pensa que usou).

    Retorna (measured_dt, sampling_rate_deviates). tolerance_fraction e a
    fracao de desvio aceitavel (0.2 = 20%).
    """
    measured_dt = float(np.mean(np.diff(t_raw)))
    sampling_rate_deviates = abs(measured_dt - dt) > tolerance_fraction * dt
    return measured_dt, sampling_rate_deviates
