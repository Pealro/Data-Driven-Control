# -*- coding: utf-8 -*-
"""Planta generica via serial, parametrizada por n,m. Fala com QUALQUER
firmware que implemente DataDrivenProtocol (firmware/boards/*) atraves de
DataDrivenSerialProtocol -- nao ha nada especifico de TCLab aqui.
tclab_siso.py, tclab_mimo.py, rc_circuit.py etc. sao especializacoes finas
desta classe: a diferenca entre elas e so n, m e os limites do atuador."""

import numpy as np

from plants.base import Plant
from plants.serial_protocol import DataDrivenSerialProtocol, SerialLink


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

    def run_experiment(self, du, dt, ubar, settle_s):
        T = du.shape[1]
        self.proto.send_config(T, dt, ubar, settle_s)
        self.proto.send_excitation(du, echo=self.verbose)

        if self.verbose:
            print(f"\n[settle] assentando em ubar = {np.round(ubar, 2)} por {settle_s} s...")

        def on_settle_progress(line):
            if self.verbose:
                _, t_s, *y_vals = line.split(",")
                print(f"    assentando... t = {t_s:>4} s | y = {y_vals}", end="\r")

        ybar = self.proto.go_and_settle(on_progress=on_settle_progress)
        if self.verbose:
            print(f"\n    Equilibrio medido: ybar = {np.round(ybar, 3)}")

        def on_sample(k, y_vals, u_vals):
            if self.verbose:
                print(f"    k = {k:>3}/{T} | y = {y_vals} | u = {u_vals}", end="\r")

        t_raw, y_raw, u_raw = self.proto.collect_experiment(T, on_sample=on_sample)
        if self.verbose:
            print("\n    Coleta concluida. Arduino aguardando K.")
        return ybar, t_raw, y_raw, u_raw

    def run_control(self, K, setpoint, duration_s):
        setpoint = np.asarray(setpoint, dtype=float)

        def on_sample(t_s, y_vals, u_vals):
            if self.verbose:
                err = np.array(y_vals) - setpoint
                print(
                    f"    t = {t_s:>7.1f} s | y = {y_vals} | u = {u_vals} | erro = {err}",
                    end="\r",
                )

        t_log, y_log, u_log = self.proto.send_gain_and_stream(
            K, setpoint, duration_s, on_sample=on_sample
        )
        if self.verbose:
            print("\n    Controle encerrado pelo Arduino.")
        return t_log, y_log, u_log

    def abort(self):
        self.proto.abort()

    def close(self):
        self.link.close()
