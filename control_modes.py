# -*- coding: utf-8 -*-
"""Bloco D: os 3 modos de teste de controle -- setpoint via terminal,
scrollbar do mouse, funcao de entrada f(t). Todos usam o mesmo mecanismo
por baixo: on_sample devolve um novo setpoint (comando SP ao firmware,
ver plants/serial_protocol.py), should_abort encerra com 'e' no terminal.

Em qualquer modo, so mandamos SP quando o valor realmente muda -- a funcao
de entrada, por exemplo, seria avaliada a CADA amostra; sem essa checagem,
mandariamos um SP por amostra (dobrando o trafego serial e arriscando o
orcamento de tempo que validamos com tanto cuidado nesta sessao).
"""

import math
import os

import numpy as np

from live_plot import LiveControlPlot
from output_io import save_control_test_csv
from terminal_input import TerminalController

SAFE_MATH_NAMESPACE = {name: getattr(math, name) for name in dir(math) if not name.startswith("_")}
SETPOINT_CHANGE_EPSILON = 1e-6


def make_function_evaluator(expression: str, max_output: float):
    """Compila f(t) uma vez (t em segundos, so math.* disponivel -- SEM
    __builtins__, para nao permitir execucao arbitraria de codigo).

    Se o valor cru sair de [0, max_output], reinicia o relogio local da
    funcao (t volta a 0) -- funcoes nao periodicas (ex.: uma rampa) viram
    repetitivas automaticamente ao bater no teto/piso.
    """
    code = compile(expression, "<setpoint_function>", "eval")
    reset_at = [0.0]

    def evaluate_raw(t: float) -> float:
        namespace = dict(SAFE_MATH_NAMESPACE)
        namespace["t"] = t
        return eval(code, {"__builtins__": {}}, namespace)

    def evaluate(elapsed_time_s: float) -> float:
        t = elapsed_time_s - reset_at[0]
        raw = evaluate_raw(t)
        if raw < 0.0 or raw > max_output:
            reset_at[0] = elapsed_time_s
            raw = evaluate_raw(0.0)
        return min(max(raw, 0.0), max_output)

    return evaluate


def _finish(plant_name, folder_path, timestamp, t_log, y_log, u_log, plot):
    png_path = os.path.join(folder_path, f"{plant_name}_{timestamp}_teste_de_controle.png")
    plot.close(keep_open=True, save_path=png_path)
    if len(t_log) > 0:
        csv_path = save_control_test_csv(folder_path, plant_name, timestamp, t_log, y_log, u_log)
        print(f"\nSalvos: {csv_path}, {png_path}")
    return t_log, y_log, u_log


def run_terminal_setpoint_mode(plant, K, initial_setpoint, plant_name, folder_path, timestamp):
    n = len(initial_setpoint)
    print(
        f"\nDigite {n} valor(es) de setpoint (separados por espaco) a qualquer momento e "
        "pressione Enter para atualizar. Digite 'e' e Enter para encerrar o teste."
    )
    terminal = TerminalController(n=n, accept_setpoint_input=True)
    terminal.start()
    plot = LiveControlPlot(plant_name, m=plant.m, setpoint_initial=float(initial_setpoint[0]))

    def on_sample(t_s, y_vals, u_vals):
        plot.add_sample(t_s, y_vals[0], u_vals)
        new_setpoint = terminal.take_pending_setpoint()
        if new_setpoint is not None:
            plot.add_sample(t_s, y_vals[0], u_vals, setpoint_val=new_setpoint[0])
        return new_setpoint

    t_log, y_log, u_log = plant.run_control(
        K, initial_setpoint, duration_s=0, on_sample=on_sample, should_abort=terminal.should_abort
    )
    return _finish(plant_name, folder_path, timestamp, t_log, y_log, u_log, plot)


def run_slider_mode(plant, K, initial_setpoint, plant_name, folder_path, timestamp, slider_range):
    n = len(initial_setpoint)
    terminal = TerminalController(n=n, accept_setpoint_input=False)
    terminal.start()
    print("\nArraste o slider para mudar o setpoint. Digite 'e' e Enter no terminal para encerrar.")
    plot = LiveControlPlot(
        plant_name,
        m=plant.m,
        setpoint_initial=float(initial_setpoint[0]),
        with_slider=True,
        slider_range=slider_range,
    )

    def on_sample(t_s, y_vals, u_vals):
        new_value = plot.take_slider_change()
        if new_value is not None:
            plot.add_sample(t_s, y_vals[0], u_vals, setpoint_val=new_value)
            return [new_value] * n
        plot.add_sample(t_s, y_vals[0], u_vals)
        return None

    t_log, y_log, u_log = plant.run_control(
        K, initial_setpoint, duration_s=0, on_sample=on_sample, should_abort=terminal.should_abort
    )
    return _finish(plant_name, folder_path, timestamp, t_log, y_log, u_log, plot)


def run_function_mode(plant, K, initial_setpoint, plant_name, folder_path, timestamp, max_output):
    n = len(initial_setpoint)
    expression = input(
        "\nDigite f(t) em segundos, saida entre 0 e "
        f"{max_output} (ex.: 5*sin(2*pi*t/10)+{max_output / 2:.1f}): "
    ).strip()
    evaluate = make_function_evaluator(expression, max_output)

    terminal = TerminalController(n=n, accept_setpoint_input=False)
    terminal.start()
    print("Rodando com setpoint(t) = f(t). Digite 'e' e Enter no terminal para encerrar.")
    plot = LiveControlPlot(plant_name, m=plant.m, setpoint_initial=float(initial_setpoint[0]))

    last_sent = [None]

    def on_sample(t_s, y_vals, u_vals):
        new_value = evaluate(t_s)
        if last_sent[0] is None or abs(new_value - last_sent[0]) > SETPOINT_CHANGE_EPSILON:
            last_sent[0] = new_value
            plot.add_sample(t_s, y_vals[0], u_vals, setpoint_val=new_value)
            return [new_value] * n
        plot.add_sample(t_s, y_vals[0], u_vals)
        return None

    t_log, y_log, u_log = plant.run_control(
        K, initial_setpoint, duration_s=0, on_sample=on_sample, should_abort=terminal.should_abort
    )
    return _finish(plant_name, folder_path, timestamp, t_log, y_log, u_log, plot)
