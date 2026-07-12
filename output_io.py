# -*- coding: utf-8 -*-
"""Bloco C: organizacao dos resultados em pasta -- uma pasta por teste,
nomeada <planta>_<timestamp>, com um CSV de aquisicao e (se chegar la) um
CSV de controle dentro dela."""

import csv
import os
from datetime import datetime

import numpy as np


def create_test_folder(plant_name: str, base_dir: str = ".") -> tuple[str, str]:
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
) -> str:
    n, m = y_raw.shape[0], u_raw.shape[0]
    T = u_raw.shape[1]
    state_deviation = y_raw - ybar.reshape(n, 1)

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
        csv_writer.writerow(header)
        for k in range(T):
            row = (
                [k, t_raw[k]]
                + list(y_raw[:, k])
                + list(u_raw[:, k])
                + list(state_deviation[:, k])
                + list(u_raw[:, k] - ubar)
            )
            csv_writer.writerow(row)
        csv_writer.writerow(
            [T, t_raw[T]]
            + list(y_raw[:, T])
            + [""] * m
            + list(state_deviation[:, T])
            + [""] * m
        )
    return csv_path


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
