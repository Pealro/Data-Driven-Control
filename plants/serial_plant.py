# -*- coding: utf-8 -*-
"""Planta generica via serial, parametrizada por n,m. Fala com QUALQUER
firmware que implemente DataDrivenProtocol (firmware/boards/*) atraves de
DataDrivenSerialProtocol -- nao ha nada especifico de TCLab aqui.
tclab_siso.py, tclab_mimo.py, rc_circuit.py etc. sao especializacoes finas
desta classe: a diferenca entre elas e so n, m e os limites do atuador."""

import time

import numpy as np

from plants.base import Plant
from plants.serial_protocol import DataDrivenSerialProtocol, SerialLink

VERBOSE_PRINT_INTERVAL_S = 0.1  # throttle dos prints de progresso: imprimir a
# CADA amostra (ex.: 200x/s com dt=5ms) gasta tempo de console dentro do laco
# que le a serial -- se o laco atrasar, o buffer de saida do Arduino enche e o
# Serial.print() do firmware trava, congelando o experimento/controle real


class SerialPlant(Plant):
    def __init__(
        self,
        n: int,
        m: int,
        port: str,
        baud: int = 115200,
        u_min: float = 0.0,
        u_max: float = 100.0,
        verbose: bool = True,
    ):
        self.n = n
        self.m = m
        self.u_min = u_min  # limites do atuador (firmware satura com constrain(pct,u_min,u_max))
        self.u_max = u_max
        self.link = SerialLink(port, baud, timeout_s=5.0)
        self.proto = DataDrivenSerialProtocol(self.link, n=n, m=m)
        self.verbose = verbose
        self._last_verbose_print = 0.0
        self._dt = None  # taxa da coleta, reusada no controle pautado pelo PC

    def _verbose_due(self) -> bool:
        if not self.verbose:
            return False
        now = time.monotonic()
        if now - self._last_verbose_print < VERBOSE_PRINT_INTERVAL_S:
            return False
        self._last_verbose_print = now
        return True

    def run_experiment(
        self, T, dt, ubar, settle_duration_s, excitation_amplitude, seed, on_sample=None
    ):
        self._dt = dt  # guardado para o controle pautado pelo PC (run_control_external)
        self.proto.send_config(T, dt, ubar, settle_duration_s, excitation_amplitude, seed)

        if self.verbose:
            print(
                f"\n[settle] assentando em ubar = {np.round(ubar, 2)} por "
                f"{settle_duration_s} s... (excitacao gerada no firmware: "
                f"excitation_amplitude={excitation_amplitude}, seed={seed})"
            )

        def on_settle_progress(line):
            if self.verbose:
                _, t_s, *y_vals = line.split(",")
                print(f"    assentando... t = {t_s:>4} s | y = {y_vals}", end="\r")

        ybar = self.proto.go_and_settle(on_progress=on_settle_progress)
        if self.verbose:
            print(f"\n    Equilibrio medido: ybar = {np.round(ybar, 3)}")

        def wrapped_on_sample(k, t_s, y_vals, u_vals):
            if self._verbose_due():
                print(f"    k = {k:>3}/{T} | y = {y_vals} | u = {u_vals}", end="\r")
            if on_sample:
                on_sample(t_s, y_vals, u_vals)

        t_raw, y_raw, u_raw = self.proto.collect_experiment(T, on_sample=wrapped_on_sample)
        if self.verbose:
            print("\n    Coleta concluida. Arduino aguardando K.")
        return ybar, t_raw, y_raw, u_raw

    def run_control(self, K, setpoint, duration_s, on_sample=None, should_abort=None):
        current_setpoint = np.asarray(setpoint, dtype=float).copy()

        def wrapped_on_sample(t_s, y_vals, u_vals):
            nonlocal current_setpoint
            new_setpoint = on_sample(t_s, y_vals, u_vals) if on_sample else None
            if new_setpoint is not None:
                current_setpoint = np.asarray(new_setpoint, dtype=float)
            if self._verbose_due():
                tracking_error = np.array(y_vals) - current_setpoint
                print(
                    f"    t = {t_s:>7.1f} s | y = {y_vals} | u = {u_vals} | "
                    f"erro = {tracking_error}",
                    end="\r",
                )
            return new_setpoint

        t_log, y_log, u_log = self.proto.send_gain_and_stream(
            K,
            current_setpoint,
            duration_s,
            on_sample=wrapped_on_sample,
            should_abort=should_abort,
        )
        if self.verbose:
            print("\n    Controle encerrado pelo Arduino.")
        return t_log, y_log, u_log

    def run_control_external(self, compute_u, duration_s, on_sample=None, should_abort=None):
        """Controle pautado pelo PC (firmware em EXTCONTROL): a lei u=compute_u(y)
        roda no PC (Koopman racional / delay-embedding). Mesma assinatura das
        plantas simuladas, para o runner tratar todas igual. Usa o dt da coleta
        (run_experiment) como taxa alvo -- o firmware pauta por millis() e, se o
        round-trip serial for maior que dt, o dt efetivo vira o do round-trip
        (o EC carrega o t_ms real, entao o log reflete o timing verdadeiro)."""
        if self._dt is None:
            raise RuntimeError("run_experiment() deve ser chamado antes de run_control_external().")

        def wrapped_on_sample(t_s, y_vals, u_vals):
            if self._verbose_due():
                print(f"    t = {t_s:>7.2f} s | y = {y_vals} | u = {u_vals}", end="\r")
            if on_sample:
                on_sample(t_s, y_vals, u_vals)

        t_log, y_log, u_log = self.proto.send_external_control_and_stream(
            self._dt, duration_s, compute_u,
            on_sample=wrapped_on_sample, should_abort=should_abort,
        )
        if self.verbose:
            print("\n    Controle (pautado pelo PC) encerrado.")
        return t_log, y_log, u_log

    def abort(self):
        self.proto.abort()

    def close(self):
        self.link.close()
