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

import calibration
from live_plot import LiveControlPlot
from output_io import save_control_test_csv
from terminal_input import TerminalController

SAFE_MATH_NAMESPACE = {name: getattr(math, name) for name in dir(math) if not name.startswith("_")}
SETPOINT_CHANGE_EPSILON = 1e-6
SETPOINT_SEND_MIN_INTERVAL_S = 0.05  # modo funcao: uma f(t) continua (ex.: seno)
# muda mais que o epsilon a CADA amostra, entao so o epsilon nao segura nada --
# sem este intervalo minimo, cada amostra viraria um par SP/ACK,SP extra na
# serial (dobrando o trafego com dt pequeno). 20 SPs/s e mais que suficiente
# para o setpoint parecer continuo.


def make_function_evaluator(expression: str, min_output: float, max_output: float):
    """Compila f(t) uma vez (t em segundos, so math.* disponivel -- SEM
    __builtins__, para nao permitir execucao arbitraria de codigo).

    Se o valor cru sair de [min_output, max_output], reinicia o relogio
    local da funcao (t volta a 0) -- funcoes nao periodicas (ex.: uma
    rampa) viram repetitivas automaticamente ao bater no teto/piso.
    """
    code = compile(expression, "<setpoint_function>", "eval")
    reset_at = [0.0]
    # namespace reusado entre chamadas (so "t" muda) -- copiar o dict de ~60
    # funcoes do math a cada amostra seria custo desnecessario no laco quente
    namespace = dict(SAFE_MATH_NAMESPACE)

    def evaluate_raw(t: float) -> float:
        namespace["t"] = t
        return eval(code, {"__builtins__": {}}, namespace)

    def evaluate(elapsed_time_s: float) -> float:
        t = elapsed_time_s - reset_at[0]
        raw = evaluate_raw(t)
        if raw < min_output or raw > max_output:
            reset_at[0] = elapsed_time_s
            raw = evaluate_raw(0.0)
        return min(max(raw, min_output), max_output)

    return evaluate


def _finish(
    plant_name, folder_path, timestamp, t_log, y_log, u_log, plot,
    y_physical_min=None, y_physical_max=None, u_physical_min=None, u_physical_max=None,
):
    # y_log/u_log vem de plant.run_control em unidade crua -- converte para
    # unidade fisica antes de salvar (identidade se a calibracao nao foi
    # definida, ver calibration.py). O plot ja recebeu valores fisicos via
    # add_sample em cada on_sample abaixo.
    y_log_physical = calibration.y_raw_to_physical(y_log, y_physical_min, y_physical_max)
    u_log_physical = calibration.u_raw_to_physical(u_log, u_physical_min, u_physical_max)
    png_path = os.path.join(folder_path, f"{plant_name}_{timestamp}_teste_de_controle.png")
    plot.close(keep_open=True, save_path=png_path)
    if len(t_log) > 0:
        csv_path = save_control_test_csv(
            folder_path, plant_name, timestamp, t_log, y_log_physical, u_log_physical
        )
        print(f"\nSalvos: {csv_path}, {png_path}")
    return t_log, y_log_physical, u_log_physical


def run_terminal_setpoint_mode(
    plant, K, initial_setpoint, plant_name, folder_path, timestamp,
    setpoint_min, setpoint_max,
    y_physical_min=None, y_physical_max=None, u_physical_min=None, u_physical_max=None,
):
    """initial_setpoint e os valores digitados pelo usuario estao em unidade
    fisica (se calibrada); sao convertidos para unidade crua antes de
    qualquer comunicacao com a planta/firmware. setpoint_min/setpoint_max
    (unidade fisica) vem da calibracao definida no Bloco A -- valores
    digitados fora dessa faixa sao ajustados (clamp) para o limite mais
    proximo."""
    n = len(initial_setpoint)
    print(
        f"\nDigite {n} valor(es) de setpoint (separados por espaco) a qualquer momento e "
        f"pressione Enter para atualizar (faixa valida: [{setpoint_min}, {setpoint_max}]). "
        "Digite 'e' e Enter para encerrar o teste."
    )
    terminal = TerminalController(n=n, accept_setpoint_input=True)
    terminal.start()
    plot = LiveControlPlot(plant_name, n=n, m=plant.m, setpoint_initial=initial_setpoint)

    def on_sample(t_s, y_vals, u_vals):
        y_physical = [calibration.y_raw_to_physical(v, y_physical_min, y_physical_max) for v in y_vals]
        u_physical = [calibration.u_raw_to_physical(v, u_physical_min, u_physical_max) for v in u_vals]
        new_setpoint_physical = terminal.take_pending_setpoint()
        setpoint_val_for_plot = None
        raw_setpoint_to_send = None
        if new_setpoint_physical is not None:
            clamped_setpoint = [min(max(v, setpoint_min), setpoint_max) for v in new_setpoint_physical]
            if clamped_setpoint != new_setpoint_physical:
                print(f"    (setpoint fora da faixa [{setpoint_min}, {setpoint_max}] -- ajustado para {clamped_setpoint})")
            setpoint_val_for_plot = clamped_setpoint
            raw_setpoint_to_send = [
                calibration.y_physical_to_raw(v, y_physical_min, y_physical_max)
                for v in clamped_setpoint
            ]
        plot.add_sample(t_s, y_physical, u_physical, setpoint_val=setpoint_val_for_plot)
        return raw_setpoint_to_send

    initial_setpoint_raw = [
        calibration.y_physical_to_raw(v, y_physical_min, y_physical_max) for v in initial_setpoint
    ]
    t_log, y_log, u_log = plant.run_control(
        K, initial_setpoint_raw, duration_s=0, on_sample=on_sample, should_abort=terminal.should_abort
    )
    return _finish(
        plant_name, folder_path, timestamp, t_log, y_log, u_log, plot,
        y_physical_min, y_physical_max, u_physical_min, u_physical_max,
    )


def run_slider_mode(
    plant, K, initial_setpoint, plant_name, folder_path, timestamp, slider_range,
    y_physical_min=None, y_physical_max=None, u_physical_min=None, u_physical_max=None,
):
    """slider_range e initial_setpoint estao em unidade fisica (se
    calibrada); convertidos para unidade crua antes de falar com a planta."""
    n = len(initial_setpoint)
    terminal = TerminalController(n=n, accept_setpoint_input=False)
    terminal.start()
    print("\nArraste o slider para mudar o setpoint. Digite 'e' e Enter no terminal para encerrar.")
    plot = LiveControlPlot(
        plant_name,
        n=n,
        m=plant.m,
        setpoint_initial=initial_setpoint,
        with_slider=True,
        slider_range=slider_range,
    )

    def on_sample(t_s, y_vals, u_vals):
        y_physical = [calibration.y_raw_to_physical(v, y_physical_min, y_physical_max) for v in y_vals]
        u_physical = [calibration.u_raw_to_physical(v, u_physical_min, u_physical_max) for v in u_vals]
        new_value_physical = plot.take_slider_change()
        if new_value_physical is not None:
            plot.add_sample(t_s, y_physical, u_physical, setpoint_val=[new_value_physical] * n)
            new_value_raw = calibration.y_physical_to_raw(
                new_value_physical, y_physical_min, y_physical_max
            )
            return [new_value_raw] * n
        plot.add_sample(t_s, y_physical, u_physical)
        return None

    initial_setpoint_raw = [
        calibration.y_physical_to_raw(v, y_physical_min, y_physical_max) for v in initial_setpoint
    ]
    t_log, y_log, u_log = plant.run_control(
        K, initial_setpoint_raw, duration_s=0, on_sample=on_sample, should_abort=terminal.should_abort
    )
    return _finish(
        plant_name, folder_path, timestamp, t_log, y_log, u_log, plot,
        y_physical_min, y_physical_max, u_physical_min, u_physical_max,
    )


def run_function_mode(
    plant, K, initial_setpoint, plant_name, folder_path, timestamp, setpoint_min, setpoint_max,
    y_physical_min=None, y_physical_max=None, u_physical_min=None, u_physical_max=None,
):
    """f(t) e initial_setpoint estao em unidade fisica (se calibrada);
    convertidos para unidade crua antes de falar com a planta.
    setpoint_min/setpoint_max (unidade fisica) vem da calibracao definida
    no Bloco A -- a saida de f(t) e sempre limitada a essa faixa (ver
    make_function_evaluator)."""
    n = len(initial_setpoint)
    expression = input(
        f"\nDigite f(t) em segundos, saida entre {setpoint_min} e "
        f"{setpoint_max} (ex.: 5*sin(2*pi*t/10)+{(setpoint_min + setpoint_max) / 2:.1f}): "
    ).strip()
    evaluate = make_function_evaluator(expression, setpoint_min, setpoint_max)

    terminal = TerminalController(n=n, accept_setpoint_input=False)
    terminal.start()
    print("Rodando com setpoint(t) = f(t). Digite 'e' e Enter no terminal para encerrar.")
    plot = LiveControlPlot(plant_name, n=n, m=plant.m, setpoint_initial=initial_setpoint)

    last_sent_value = [None]
    last_sent_time = [-SETPOINT_SEND_MIN_INTERVAL_S]

    def on_sample(t_s, y_vals, u_vals):
        y_physical = [calibration.y_raw_to_physical(v, y_physical_min, y_physical_max) for v in y_vals]
        u_physical = [calibration.u_raw_to_physical(v, u_physical_min, u_physical_max) for v in u_vals]
        new_value_physical = evaluate(t_s)
        value_changed = (
            last_sent_value[0] is None
            or abs(new_value_physical - last_sent_value[0]) > SETPOINT_CHANGE_EPSILON
        )
        interval_elapsed = t_s - last_sent_time[0] >= SETPOINT_SEND_MIN_INTERVAL_S
        if value_changed and interval_elapsed:
            last_sent_value[0] = new_value_physical
            last_sent_time[0] = t_s
            plot.add_sample(t_s, y_physical, u_physical, setpoint_val=[new_value_physical] * n)
            new_value_raw = calibration.y_physical_to_raw(
                new_value_physical, y_physical_min, y_physical_max
            )
            return [new_value_raw] * n
        plot.add_sample(t_s, y_physical, u_physical)
        return None

    initial_setpoint_raw = [
        calibration.y_physical_to_raw(v, y_physical_min, y_physical_max) for v in initial_setpoint
    ]
    t_log, y_log, u_log = plant.run_control(
        K, initial_setpoint_raw, duration_s=0, on_sample=on_sample, should_abort=terminal.should_abort
    )
    return _finish(
        plant_name, folder_path, timestamp, t_log, y_log, u_log, plot,
        y_physical_min, y_physical_max, u_physical_min, u_physical_max,
    )
