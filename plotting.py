# -*- coding: utf-8 -*-
"""Graficos do experimento + malha fechada. Layout escala com n (estados)
e m (entradas): uma linha por estado, uma linha por entrada."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_results(
    out_path,
    plant_name: str,
    ke: np.ndarray,
    y_raw: np.ndarray,
    ybar: np.ndarray,
    u_raw: np.ndarray,
    ubar: np.ndarray,
    t_log,
    y_log: np.ndarray,
    u_log: np.ndarray,
    setpoint: np.ndarray,
    rho: float,
):
    n, m = y_raw.shape[0], u_raw.shape[0]
    rows = n + m
    fig, ax = plt.subplots(rows, 2, figsize=(12, 3.2 * rows), squeeze=False)

    for i in range(n):
        a = ax[i, 0]
        a.plot(ke, y_raw[i], ".-")
        a.axhline(ybar[i], color="k", lw=0.7, ls="--", label=r"$\bar{y}$")
        a.set_title(f"Experimento: y{i + 1}")
        a.set_ylabel(f"y{i + 1}")
        a.legend()
        a.grid(alpha=0.3)

    for j in range(m):
        a = ax[n + j, 0]
        a.step(ke[:-1], u_raw[j], where="post", color="tab:red")
        a.axhline(ubar[j], color="k", lw=0.7, ls="--", label=r"$\bar{u}$")
        a.set_title(f"Experimento: u{j + 1}")
        a.set_ylabel(f"u{j + 1}")
        a.set_xlabel("tempo [s]")
        a.legend()
        a.grid(alpha=0.3)

    if len(t_log) > 0:
        for i in range(n):
            a = ax[i, 1]
            a.plot(t_log, y_log[i])
            a.axhline(setpoint[i], color="k", lw=0.7, ls="--", label="setpoint")
            a.set_title(f"Malha fechada: y{i + 1}")
            a.set_ylabel(f"y{i + 1}")
            a.legend()
            a.grid(alpha=0.3)

        for j in range(m):
            a = ax[n + j, 1]
            a.step(t_log, u_log[j], where="post", color="tab:red")
            a.axhline(ubar[j], color="k", lw=0.7, ls="--", label=r"$\bar{u}$")
            a.set_title(f"Malha fechada: u{j + 1}")
            a.set_ylabel(f"u{j + 1}")
            a.set_xlabel("tempo [s]")
            a.legend()
            a.grid(alpha=0.3)
    else:
        for i in range(rows):
            ax[i, 1].axis("off")

    fig.suptitle(
        f"Controle data-driven ({plant_name}) -- De Persis & Tesi, Thm 6, rho={rho}"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
