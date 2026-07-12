# -*- coding: utf-8 -*-
"""Ponto de entrada generico: escolhe planta+config, roda o fluxo completo
data-driven (excitacao -> assentamento+experimento -> assembly -> LMI ->
controle -> salvar). Nao muda entre plantas -- so o modulo de config muda.

Uso:
    python runner.py --config config.tclab_siso
    python runner.py --config config.simulated_2x2
"""

import argparse
import csv
import importlib
import sys

import numpy as np

from datadriven import assembly, diagnostics, lmi
from plotting import plot_results


def parse_args():
    parser = argparse.ArgumentParser(
        description="Controle data-driven (Teorema 6, De Persis & Tesi)"
    )
    parser.add_argument(
        "--config",
        default="config.rc_circuit",
        help="modulo dotted path da config da planta (ex.: config.tclab_siso)",
    )
    parser.add_argument(
        "--out-prefix",
        default="",
        help="prefixo dos arquivos de saida, para nao colidir entre plantas "
        "(ex.: --out-prefix rc_circuit_ gera rc_circuit_dados_experimento.csv)",
    )
    return parser.parse_args()


def save_csvs(t_raw, y_raw, u_raw, ybar, ubar, t_log, y_log, u_log, out_prefix=""):
    n, m = y_raw.shape[0], u_raw.shape[0]
    T = u_raw.shape[1]
    state_deviation = y_raw - ybar.reshape(n, 1)

    with open(f"{out_prefix}dados_experimento.csv", "w", newline="") as csv_file:
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

    with open(f"{out_prefix}dados_controle.csv", "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        header = ["t_s"] + [f"y{i + 1}" for i in range(n)] + [f"u{j + 1}" for j in range(m)]
        csv_writer.writerow(header)
        for k in range(len(t_log)):
            csv_writer.writerow([t_log[k]] + list(y_log[:, k]) + list(u_log[:, k]))


def main():
    args = parse_args()
    cfg = importlib.import_module(args.config).CONFIG

    print("=" * 70)
    print(f" Controle data-driven -- planta: {cfg.name}")
    print("=" * 70)
    print(
        f" T = {cfg.T} | dt = {cfg.dt} s | excitation_amplitude = {cfg.excitation_amplitude} | "
        f"max_expected_state_deviation = {cfg.max_expected_state_deviation} | rho = {cfg.rho}"
    )
    print(
        f" ubar = {cfg.ubar} | assentamento = {cfg.settle_duration_s} s | "
        f"controle = {cfg.control_duration_s} s"
    )
    print(f" duracao do experimento: {cfg.T * cfg.dt:.0f} s")

    plant = cfg.make_plant()
    n, m = plant.n, plant.m

    try:
        print(f"\n[1] Assentando e coletando experimento ({cfg.T} passos de {cfg.dt} s)...")
        ybar, t_raw, y_raw, u_raw = plant.run_experiment(
            cfg.T,
            cfg.dt,
            cfg.ubar,
            cfg.settle_duration_s,
            cfg.excitation_amplitude,
            cfg.seed,
        )
    except KeyboardInterrupt:
        print("\nAbortado pelo usuario durante o experimento.")
        if hasattr(plant, "abort"):
            plant.abort()
        plant.close()
        sys.exit(1)

    measured_dt, sampling_rate_deviates = diagnostics.check_sampling_rate(t_raw, cfg.dt)
    if sampling_rate_deviates:
        print(
            f"    AVISO: dt real medido ({measured_dt * 1000:.2f} ms) difere do dt configurado "
            f"({cfg.dt * 1000:.2f} ms) em mais de 20%. O laco provavelmente ficou limitado "
            "pelo tempo de execucao (leitura + Serial.print), nao pelo relogio -- aumente dt "
            "ou reduza o overhead por passo (ex.: menos amostras de oversampling)."
        )

    X0, X1, U0 = assembly.build_X0_X1_U0(y_raw, u_raw, ybar, cfg.ubar)

    saturated_sample_count = diagnostics.check_saturation(
        u_raw, getattr(plant, "u_min", None), getattr(plant, "u_max", None)
    )
    if saturated_sample_count > 0:
        print(
            f"    AVISO: {saturated_sample_count} amostras saturaram. U0 usa o valor aplicado"
            " (correto), mas considere reduzir excitation_amplitude."
        )

    max_state_deviation, exceeded_expected_deviation = diagnostics.check_excursion(
        X0, X1, cfg.max_expected_state_deviation
    )
    print(
        f"\n[2] Excursao maxima do estado: |dx|_max = {max_state_deviation:.3f} "
        f"(limite max_expected_state_deviation = {cfg.max_expected_state_deviation})"
    )
    if exceeded_expected_deviation:
        print(
            "    AVISO: excursao acima de max_expected_state_deviation -- os dados podem"
            " violar a hipotese de resto pequeno (Assumption 5). Considere reduzir"
            " excitation_amplitude/dt ou aumentar settle_duration_s."
        )

    rank, is_persistently_exciting = diagnostics.check_persistency_of_excitation(U0, X0, n, m)
    print(f"    rank([U0; X0]) = {rank}  (necessario n+m = {n + m})")
    if not is_persistently_exciting:
        plant.close()
        sys.exit("Dados nao persistentemente excitantes; aumente T ou excitation_amplitude.")

    gamma_hat = diagnostics.estimate_residual_gamma(X0, X1, U0)
    print(f"    gamma estimado (proxy Assumption 5) ~ {gamma_hat:.2e}")

    print(f"\n[3] Resolvendo a LMI data-driven (rho = {cfg.rho})...")
    try:
        result = lmi.solve_gain(X0, X1, U0, cfg.rho)
    except lmi.LMIInfeasibleError as error:
        if hasattr(plant, "abort"):
            plant.abort()
        plant.close()
        sys.exit(str(error))
    print(f"    LMI solve status: {result.status}")
    print(f"    Ganho data-driven K =\n{result.K}")

    closed_loop_eigenvalues, stable, within_stability_margin = lmi.verify_stability(
        X1, result.G_K, cfg.rho
    )
    print(
        f"\n[4] |autoval.| (dados): {np.round(np.abs(closed_loop_eigenvalues), 4)} | "
        f"estavel: {stable} | dentro da margem rho: {within_stability_margin}"
    )
    if not stable:
        if hasattr(plant, "abort"):
            plant.abort()
        plant.close()
        sys.exit("Verificacao data-driven falhou: malha fechada instavel.")

    setpoint = ybar if cfg.setpoint is None else cfg.setpoint
    if cfg.setpoint is not None and np.max(np.abs(setpoint - ybar)) > cfg.max_expected_state_deviation:
        print(
            f"    AVISO: |setpoint - ybar| max = {np.max(np.abs(setpoint - ybar)):.2f} >"
            " max_expected_state_deviation. Realimentacao de estados pura tera offset em"
            " regime; o ganho foi validado localmente em torno de ybar."
        )

    print(
        f"\n[5] Controle em malha fechada. Setpoint = {setpoint}, "
        f"duracao = {cfg.control_duration_s} s."
    )
    try:
        t_log, y_log, u_log = plant.run_control(result.K, setpoint, cfg.control_duration_s)
    except KeyboardInterrupt:
        print("\nAbortado pelo usuario durante o controle.")
        if hasattr(plant, "abort"):
            plant.abort()
        t_log, y_log, u_log = [], np.zeros((n, 0)), np.zeros((m, 0))
    finally:
        plant.close()

    if len(t_log) > 1:
        measured_control_dt, control_sampling_rate_deviates = diagnostics.check_sampling_rate(
            np.array(t_log), cfg.dt
        )
        if control_sampling_rate_deviates:
            print(
                f"    AVISO: dt real medido na malha fechada ({measured_control_dt * 1000:.2f} ms)"
                f" difere do dt configurado ({cfg.dt * 1000:.2f} ms) em mais de 20%."
            )

    save_csvs(
        t_raw, y_raw, u_raw, ybar, cfg.ubar, t_log, y_log, u_log, out_prefix=args.out_prefix
    )

    plot_results(
        f"{args.out_prefix}tclab_datadriven_resultado.png",
        cfg.name,
        t_raw,
        y_raw,
        ybar,
        u_raw,
        cfg.ubar,
        t_log,
        y_log,
        u_log,
        setpoint,
        cfg.rho,
    )
    print(
        f"\nSalvos: {args.out_prefix}dados_experimento.csv, {args.out_prefix}dados_controle.csv, "
        f"{args.out_prefix}tclab_datadriven_resultado.png"
    )


if __name__ == "__main__":
    main()
