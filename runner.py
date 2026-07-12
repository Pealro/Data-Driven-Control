# -*- coding: utf-8 -*-
"""Ponto de entrada: assistente interativo (Bloco A) -> aquisicao com plot
ao vivo (Bloco B) -> pasta/CSV + confirmacao + LMI (Bloco C) -> testes de
controle interativos (Bloco D). Ver wizard.py, live_plot.py, output_io.py,
control_modes.py para os blocos individuais.

Uso:
    python runner.py                          # assistente interativo completo
    python runner.py --config config.rc_circuit  # pula o Bloco A, usa uma config existente
"""

import argparse
import importlib
import sys

import numpy as np

import wizard
from control_modes import run_function_mode, run_slider_mode, run_terminal_setpoint_mode
from datadriven import assembly, diagnostics, lmi
from live_plot import LiveAcquisitionPlot
from output_io import create_test_folder, save_input_test_csv
from wizard import WizardSession, prompt_choice, prompt_float


def parse_args():
    parser = argparse.ArgumentParser(
        description="Controle data-driven (Teorema 6, De Persis & Tesi)"
    )
    parser.add_argument(
        "--config",
        default=None,
        help="pula o assistente interativo (Bloco A) e usa esta config existente "
        "diretamente (ex.: config.rc_circuit)",
    )
    return parser.parse_args()


def _session_from_config(dotted_path: str) -> WizardSession:
    cfg = importlib.import_module(dotted_path).CONFIG
    return WizardSession(
        plant_name=cfg.name,
        plant=cfg.make_plant(),
        T=cfg.T,
        dt=cfg.dt,
        ubar=cfg.ubar,
        settle_duration_s=cfg.settle_duration_s,
        excitation_amplitude=cfg.excitation_amplitude,
        max_expected_state_deviation=cfg.max_expected_state_deviation,
        rho=cfg.rho,
        seed=cfg.seed,
    )


def _confirm(question: str, default_yes: bool = False) -> bool:
    suffix = "[S/n]" if default_yes else "[s/N]"
    raw = input(f"\n{question} {suffix}: ").strip().lower()
    if raw == "":
        return default_yes
    return raw in ("s", "sim", "y", "yes")


def main():
    args = parse_args()
    session = _session_from_config(args.config) if args.config else wizard.run_wizard()
    plant = session.plant
    n, m = plant.n, plant.m

    print("\n" + "=" * 70)
    print(f" Controle data-driven -- planta: {session.plant_name}")
    print("=" * 70)
    print(
        f" T = {session.T} | dt = {session.dt} s | "
        f"excitation_amplitude = {session.excitation_amplitude} | "
        f"max_expected_state_deviation = {session.max_expected_state_deviation} | rho = {session.rho}"
    )
    print(f" ubar = {session.ubar} | assentamento = {session.settle_duration_s} s")

    # ------------------------------------------------------------ Bloco B --
    print(f"\n[1] Assentando e coletando experimento ({session.T} passos de {session.dt} s)...")
    acquisition_plot = LiveAcquisitionPlot(session.plant_name, n, m)
    try:
        ybar, t_raw, y_raw, u_raw = plant.run_experiment(
            session.T,
            session.dt,
            session.ubar,
            session.settle_duration_s,
            session.excitation_amplitude,
            session.seed,
            on_sample=acquisition_plot.add_sample,
        )
    except KeyboardInterrupt:
        print("\nAbortado pelo usuario durante o experimento.")
        acquisition_plot.close()
        if hasattr(plant, "abort"):
            plant.abort()
        plant.close()
        sys.exit(1)

    measured_dt, sampling_rate_deviates = diagnostics.check_sampling_rate(t_raw, session.dt)
    if sampling_rate_deviates:
        print(
            f"    AVISO: dt real medido ({measured_dt * 1000:.2f} ms) difere do dt configurado "
            f"({session.dt * 1000:.2f} ms) em mais de 20%. O laco provavelmente ficou limitado "
            "pelo tempo de execucao (leitura + Serial.print), nao pelo relogio -- aumente dt "
            "ou reduza o overhead por passo (ex.: menos amostras de oversampling)."
        )

    saturated_sample_count = diagnostics.check_saturation(
        u_raw, getattr(plant, "u_min", None), getattr(plant, "u_max", None)
    )
    if saturated_sample_count > 0:
        print(
            f"    AVISO: {saturated_sample_count} amostras saturaram. U0 usa o valor aplicado"
            " (correto), mas considere reduzir excitation_amplitude."
        )

    # ------------------------------------------------------------ Bloco C --
    X0, X1, U0 = assembly.build_X0_X1_U0(y_raw, u_raw, ybar, session.ubar)

    max_state_deviation, exceeded_expected_deviation = diagnostics.check_excursion(
        X0, X1, session.max_expected_state_deviation
    )
    rank, is_persistently_exciting = diagnostics.check_persistency_of_excitation(U0, X0, n, m)
    gamma_hat = diagnostics.estimate_residual_gamma(X0, X1, U0)

    print(
        f"\n[2] Excursao maxima do estado: |dx|_max = {max_state_deviation:.3f} "
        f"(limite max_expected_state_deviation = {session.max_expected_state_deviation})"
    )
    if exceeded_expected_deviation:
        print(
            "    AVISO: excursao acima de max_expected_state_deviation -- os dados podem"
            " violar a hipotese de resto pequeno (Assumption 5)."
        )
    print(f"    rank([U0; X0]) = {rank}  (necessario n+m = {n + m})")
    print(f"    gamma estimado (proxy Assumption 5) ~ {gamma_hat:.2e}")

    folder_path, timestamp = create_test_folder(session.plant_name)
    input_csv_path = save_input_test_csv(
        folder_path, session.plant_name, timestamp, t_raw, y_raw, u_raw, ybar, session.ubar
    )
    acquisition_png_path = f"{folder_path}/{session.plant_name}_{timestamp}_teste_de_input.png"
    acquisition_plot.close(keep_open=False, save_path=acquisition_png_path)
    print(f"\n    Pasta: {folder_path}")
    print(f"    Salvos: {input_csv_path}, {acquisition_png_path}")

    if not is_persistently_exciting:
        print("\nAVISO: dados NAO persistentemente excitantes (rank insuficiente).")

    if not _confirm("Prosseguir com o calculo da LMI?"):
        plant.close()
        print("\nEncerrado a pedido do usuario (LMI nao calculada).")
        return

    print(f"\n[3] Resolvendo a LMI data-driven (rho = {session.rho})...")
    try:
        result = lmi.solve_gain(X0, X1, U0, session.rho)
    except lmi.LMIInfeasibleError as error:
        plant.close()
        sys.exit(str(error))
    print(f"    LMI solve status: {result.status}")
    print(f"    Ganho data-driven K =\n{result.K}")

    closed_loop_eigenvalues, stable, within_stability_margin = lmi.verify_stability(
        X1, result.G_K, session.rho
    )
    print(
        f"\n[4] |autoval.| (dados): {np.round(np.abs(closed_loop_eigenvalues), 4)} | "
        f"estavel: {stable} | dentro da margem rho: {within_stability_margin}"
    )
    if not stable:
        plant.close()
        sys.exit("Verificacao data-driven falhou: malha fechada instavel.")

    while True:
        choice = prompt_choice(
            "O que deseja fazer?", ["Mostrar autovetores", "Prosseguir com testes de controle"]
        )
        if choice == 1:
            break
        eigenvalues, eigenvectors = lmi.closed_loop_eigen(X1, result.G_K)
        print(f"\nAutovalores:\n{eigenvalues}")
        print(f"Autovetores (colunas):\n{eigenvectors}")

    # ------------------------------------------------------------ Bloco D --
    if hasattr(plant, "real_time"):
        plant.real_time = True  # planta simulada: espaca os passos por dt para
        # dar tempo real de o usuario interagir (terminal/slider) -- irrelevante
        # para plantas seriais, que ja sao pautadas pelo relogio do Arduino.

    initial_setpoint = np.array(
        [
            prompt_float(f"Setpoint inicial y{i + 1}", default=float(ybar[i]))
            for i in range(n)
        ]
    )

    mode = prompt_choice(
        "Modo de teste de controle:",
        [
            "Setpoint via terminal (digite novos valores durante o teste)",
            "Scrollbar do mouse",
            "Funcao de entrada f(t)",
        ],
    )
    if mode == 0:
        run_terminal_setpoint_mode(
            plant, result.K, initial_setpoint, session.plant_name, folder_path, timestamp
        )
    elif mode == 1:
        slider_range = (
            float(ybar[0] - session.max_expected_state_deviation),
            float(ybar[0] + session.max_expected_state_deviation),
        )
        run_slider_mode(
            plant, result.K, initial_setpoint, session.plant_name, folder_path, timestamp,
            slider_range,
        )
    else:
        max_output = prompt_float("Valor maximo de saida da funcao f(t)", default=float(ybar[0] * 2))
        run_function_mode(
            plant, result.K, initial_setpoint, session.plant_name, folder_path, timestamp,
            max_output,
        )

    plant.close()
    print("\nTeste concluido.")


if __name__ == "__main__":
    main()
