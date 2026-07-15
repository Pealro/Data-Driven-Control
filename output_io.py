# -*- coding: utf-8 -*-
"""Bloco C: organizacao dos resultados em pasta -- uma pasta por teste,
nomeada <planta>_<timestamp>, com um CSV de aquisicao e (se chegar la) um
CSV de controle dentro dela. Todas as pastas de teste ficam dentro de
experimentos/ (nunca versionado -- ver .gitignore) para nao poluir a raiz
do projeto nem o repositorio remoto com dados de coleta."""

import csv
import os
from datetime import datetime

import numpy as np

import calibration

# ancorado na pasta do projeto (nao no CWD) -- rodar runner.py de outro
# diretorio nao pode espalhar pastas de teste fora do projeto
EXPERIMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experimentos")


def create_test_folder(plant_name: str, base_dir: str = EXPERIMENTS_DIR) -> tuple[str, str]:
    """Cria (se nao existir) <base_dir>/<plant_name>_<timestamp>/ e retorna
    (caminho_da_pasta, timestamp)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_path = os.path.join(base_dir, f"{plant_name}_{timestamp}")
    os.makedirs(folder_path, exist_ok=True)
    return folder_path, timestamp


def save_input_test_csv(
    folder_path: str,
    plant_name: str,
    timestamp: str,
    t_raw: np.ndarray,
    y_raw: np.ndarray,
    u_raw: np.ndarray,
    ybar: np.ndarray,
    ubar: np.ndarray,
    y_physical_min: float | None = None,
    y_physical_max: float | None = None,
    u_physical_min: float | None = None,
    u_physical_max: float | None = None,
) -> str:
    n, m = y_raw.shape[0], u_raw.shape[0]
    T = u_raw.shape[1]
    state_deviation = y_raw - ybar.reshape(n, 1)

    # colunas extra em unidade fisica so aparecem se a calibracao (Bloco A)
    # foi definida para o respectivo lado -- ver calibration.py
    has_y_calibration = y_physical_min is not None and y_physical_max is not None
    has_u_calibration = u_physical_min is not None and u_physical_max is not None
    if has_y_calibration:
        y_physical = calibration.y_raw_to_physical(y_raw, y_physical_min, y_physical_max)
    if has_u_calibration:
        u_physical = calibration.u_raw_to_physical(u_raw, u_physical_min, u_physical_max)

    csv_path = os.path.join(folder_path, f"{plant_name}_{timestamp}_teste_de_input.csv")
    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        header = (
            ["k", "t_real_s"]
            + [f"y{i + 1}" for i in range(n)]
            + [f"u{j + 1}_aplicado" for j in range(m)]
            + [f"dy{i + 1}" for i in range(n)]
            + [f"du{j + 1}_aplicado" for j in range(m)]
        )
        if has_y_calibration:
            header += [f"y{i + 1}_fisico" for i in range(n)]
        if has_u_calibration:
            header += [f"u{j + 1}_aplicado_fisico" for j in range(m)]
        csv_writer.writerow(header)
        for k in range(T):
            row = (
                [k, t_raw[k]]
                + list(y_raw[:, k])
                + list(u_raw[:, k])
                + list(state_deviation[:, k])
                + list(u_raw[:, k] - ubar)
            )
            if has_y_calibration:
                row += list(y_physical[:, k])
            if has_u_calibration:
                row += list(u_physical[:, k])
            csv_writer.writerow(row)
        last_row = (
            [T, t_raw[T]]
            + list(y_raw[:, T])
            + [""] * m
            + list(state_deviation[:, T])
            + [""] * m
        )
        if has_y_calibration:
            last_row += list(y_physical[:, T])
        if has_u_calibration:
            last_row += [""] * m
        csv_writer.writerow(last_row)
    return csv_path


def save_gain_csv(folder_path: str, plant_name: str, timestamp: str, K: np.ndarray) -> str:
    """Salva o ganho data-driven K (m, n) na pasta do teste -- para
    reaproveitar depois (ex.: recarregar K sem refazer a coleta/LMI). K
    sempre em unidade crua (mesma convencao usada para falar com a planta/
    firmware, ver calibration.py)."""
    csv_path = os.path.join(folder_path, f"{plant_name}_{timestamp}_K.csv")
    np.savetxt(csv_path, K, delimiter=",")
    return csv_path


def save_koopman_controller(
    folder_path: str, plant_name: str, timestamp: str, K, Kw, exponents,
) -> str:
    """Salva o controlador racional de Koopman (K, Kw e os expoentes do lifting
    Phi) num .npz na pasta do teste, para recarregar sem refazer EDMD/LMI."""
    npz_path = os.path.join(folder_path, f"{plant_name}_{timestamp}_koopman.npz")
    np.savez(
        npz_path,
        K=np.asarray(K, dtype=float),
        Kw=np.asarray(Kw, dtype=float),
        exponents=np.asarray(exponents, dtype=int),
    )
    return npz_path


def save_control_test_csv(
    folder_path: str,
    plant_name: str,
    timestamp: str,
    t_log,
    y_log: np.ndarray,
    u_log: np.ndarray,
) -> str:
    n, m = y_log.shape[0], u_log.shape[0]
    csv_path = os.path.join(folder_path, f"{plant_name}_{timestamp}_teste_de_controle.csv")
    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        header = ["t_s"] + [f"y{i + 1}" for i in range(n)] + [f"u{j + 1}" for j in range(m)]
        csv_writer.writerow(header)
        for k in range(len(t_log)):
            csv_writer.writerow([t_log[k]] + list(y_log[:, k]) + list(u_log[:, k]))
    return csv_path
