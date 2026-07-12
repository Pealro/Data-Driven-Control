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
    t_raw: np.ndarray,
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
    row_count = n + m
    fig, axes = plt.subplots(row_count, 2, figsize=(12, 3.2 * row_count), squeeze=False)

    for i in range(n):
        subplot = axes[i, 0]
        subplot.plot(t_raw, y_raw[i], ".-")
        subplot.axhline(ybar[i], color="k", lw=0.7, ls="--", label=r"$\bar{y}$")
        subplot.set_title(f"Experimento: y{i + 1}")
        subplot.set_ylabel(f"y{i + 1}")
        subplot.legend()
        subplot.grid(alpha=0.3)

    for j in range(m):
        subplot = axes[n + j, 0]
        subplot.step(t_raw[:-1], u_raw[j], where="post", color="tab:red")
        subplot.axhline(ubar[j], color="k", lw=0.7, ls="--", label=r"$\bar{u}$")
        subplot.set_title(f"Experimento: u{j + 1}")
        subplot.set_ylabel(f"u{j + 1}")
        subplot.set_xlabel("tempo [s]")
        subplot.legend()
        subplot.grid(alpha=0.3)

    if len(t_log) > 0:
        for i in range(n):
            subplot = axes[i, 1]
            subplot.plot(t_log, y_log[i])
            subplot.axhline(setpoint[i], color="k", lw=0.7, ls="--", label="setpoint")
            subplot.set_title(f"Malha fechada: y{i + 1}")
            subplot.set_ylabel(f"y{i + 1}")
            subplot.legend()
            subplot.grid(alpha=0.3)

        for j in range(m):
            subplot = axes[n + j, 1]
            subplot.step(t_log, u_log[j], where="post", color="tab:red")
            subplot.axhline(ubar[j], color="k", lw=0.7, ls="--", label=r"$\bar{u}$")
            subplot.set_title(f"Malha fechada: u{j + 1}")
            subplot.set_ylabel(f"u{j + 1}")
            subplot.set_xlabel("tempo [s]")
            subplot.legend()
            subplot.grid(alpha=0.3)
    else:
        for i in range(row_count):
            axes[i, 1].axis("off")

    fig.suptitle(
        f"Controle data-driven ({plant_name}) -- De Persis & Tesi, Thm 6, rho={rho}"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
