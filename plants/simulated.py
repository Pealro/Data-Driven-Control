# -*- coding: utf-8 -*-
"""Planta simulada: espaco de estados linear discreto
    x(k+1) = A x(k) + B u(k) + ruido
sem hardware -- util para testar o algoritmo data-driven offline.
n, m sao inferidos do shape de A, B (MIMO generico)."""

import time

import numpy as np

from datadriven.excitation import generate_excitation
from plants.base import Plant


class SimulatedLinearPlant(Plant):
    def __init__(
        self,
        A,
        B,
        noise_std: float = 0.0,
        u_min: float | None = None,
        u_max: float | None = None,
        x0=None,
        seed: int | None = None,
        verbose: bool = True,
        real_time: bool = False,
    ):
        """real_time=True espaca os passos por dt (time.sleep) para imitar o
        ritmo de uma planta real -- necessario para os modos de controle
        interativo (Bloco D: slider/terminal/funcao) terem tempo real de
        responder. Falso por padrao para nao pesar testes automatizados."""
        A = np.asarray(A, dtype=float)
        B = np.asarray(B, dtype=float)
        if A.shape[0] != A.shape[1]:
            raise ValueError(f"A deve ser quadrada, recebido shape {A.shape}")
        if B.shape[0] != A.shape[0]:
            raise ValueError(f"B deve ter {A.shape[0]} linhas (n), recebido shape {B.shape}")

        self.A = A
        self.B = B
        self.n = A.shape[0]
        self.m = B.shape[1]
        self.noise_std = noise_std
        self.u_min = u_min
        self.u_max = u_max
        self.rng = np.random.default_rng(seed)
        self.x = np.zeros(self.n) if x0 is None else np.asarray(x0, dtype=float).copy()
        self.verbose = verbose
        self.real_time = real_time
        self._dt: float | None = None
        self._ubar: np.ndarray | None = None

    def _saturate(self, absolute_input: np.ndarray) -> np.ndarray:
        if self.u_min is None and self.u_max is None:
            return absolute_input
        lower_bound = -np.inf if self.u_min is None else self.u_min
        upper_bound = np.inf if self.u_max is None else self.u_max
        return np.clip(absolute_input, lower_bound, upper_bound)

    def _step(self, absolute_input: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        u_applied = self._saturate(absolute_input)
        noise = (
            self.rng.normal(0.0, self.noise_std, size=self.n) if self.noise_std > 0 else 0.0
        )
        self.x = self.A @ self.x + self.B @ u_applied + noise
        return self.x.copy(), u_applied

    def run_experiment(
        self, T, dt, ubar, settle_duration_s, excitation_amplitude, seed, on_sample=None
    ):
        input_deviation = generate_excitation(T, self.m, excitation_amplitude, seed=seed)

        self._dt = dt
        self._ubar = np.asarray(ubar, dtype=float)

        settle_step_count = (
            max(1, int(round(settle_duration_s / dt))) if settle_duration_s > 0 else 1
        )
        for _ in range(settle_step_count):
            self._step(self._ubar)
        ybar = self.x.copy()
        if self.verbose:
            print(f"    Equilibrio simulado: ybar = {np.round(ybar, 4)}")

        t_raw = np.arange(T + 1) * dt  # simulado: dt e exato, sem desvio de execucao
        y_raw = np.zeros((self.n, T + 1))
        u_raw = np.zeros((self.m, T))
        y_raw[:, 0] = self.x
        if on_sample:
            on_sample(t_raw[0], y_raw[:, 0].tolist(), self._ubar.tolist())
        for k in range(T):
            if self.real_time:
                time.sleep(dt)
            absolute_input = self._ubar + input_deviation[:, k]
            y_k, u_applied = self._step(absolute_input)
            y_raw[:, k + 1] = y_k
            u_raw[:, k] = u_applied
            if on_sample:
                on_sample(t_raw[k + 1], y_k.tolist(), u_applied.tolist())
        return ybar, t_raw, y_raw, u_raw

    def run_control(self, K, setpoint, duration_s, on_sample=None, should_abort=None):
        if self._dt is None or self._ubar is None:
            raise RuntimeError("run_experiment() deve ser chamado antes de run_control().")
        dt = self._dt
        ubar = self._ubar
        current_setpoint = np.asarray(setpoint, dtype=float).copy()
        control_step_count = int(round(duration_s / dt)) if duration_s > 0 else None

        t_log: list[float] = []
        y_log: list[np.ndarray] = []
        u_log: list[np.ndarray] = []
        elapsed_time_s, k = 0.0, 0
        try:
            while control_step_count is None or k < control_step_count:
                if self.real_time:
                    time.sleep(dt)
                y = self.x.copy()
                absolute_input = ubar + K @ (y - current_setpoint)
                _, u_applied = self._step(absolute_input)
                t_log.append(elapsed_time_s)
                y_log.append(y)
                u_log.append(u_applied)
                if on_sample:
                    new_setpoint = on_sample(elapsed_time_s, y.tolist(), u_applied.tolist())
                    if new_setpoint is not None:
                        current_setpoint = np.asarray(new_setpoint, dtype=float)
                if should_abort and should_abort():
                    break
                elapsed_time_s += dt
                k += 1
        except KeyboardInterrupt:
            if self.verbose:
                print("\n    Controle simulado interrompido pelo usuario.")

        y_log_matrix = np.array(y_log).T if y_log else np.zeros((self.n, 0))
        u_log_matrix = np.array(u_log).T if u_log else np.zeros((self.m, 0))
        return t_log, y_log_matrix, u_log_matrix

    def close(self) -> None:
        pass
