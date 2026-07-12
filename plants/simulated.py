# -*- coding: utf-8 -*-
"""Planta simulada: espaco de estados linear discreto
    x(k+1) = A x(k) + B u(k) + ruido
sem hardware -- util para testar o algoritmo data-driven offline.
n, m sao inferidos do shape de A, B (MIMO generico)."""

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
    ):
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
        self._dt: float | None = None
        self._ubar: np.ndarray | None = None

    def _saturate(self, u: np.ndarray) -> np.ndarray:
        if self.u_min is None and self.u_max is None:
            return u
        lo = -np.inf if self.u_min is None else self.u_min
        hi = np.inf if self.u_max is None else self.u_max
        return np.clip(u, lo, hi)

    def _step(self, u_abs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        u_applied = self._saturate(u_abs)
        noise = (
            self.rng.normal(0.0, self.noise_std, size=self.n) if self.noise_std > 0 else 0.0
        )
        self.x = self.A @ self.x + self.B @ u_applied + noise
        return self.x.copy(), u_applied

    def run_experiment(self, T, dt, ubar, settle_s, amp_entrada, seed):
        du = generate_excitation(T, self.m, amp_entrada, seed=seed)

        self._dt = dt
        self._ubar = np.asarray(ubar, dtype=float)

        n_settle_steps = max(1, int(round(settle_s / dt))) if settle_s > 0 else 1
        for _ in range(n_settle_steps):
            self._step(self._ubar)
        ybar = self.x.copy()
        if self.verbose:
            print(f"    Equilibrio simulado: ybar = {np.round(ybar, 4)}")

        t_raw = np.arange(T + 1) * dt  # simulado: dt e exato, sem desvio de execucao
        y_raw = np.zeros((self.n, T + 1))
        u_raw = np.zeros((self.m, T))
        y_raw[:, 0] = self.x
        for k in range(T):
            u_abs = self._ubar + du[:, k]
            y_k, u_applied = self._step(u_abs)
            y_raw[:, k + 1] = y_k
            u_raw[:, k] = u_applied
        return ybar, t_raw, y_raw, u_raw

    def run_control(self, K, setpoint, duration_s):
        if self._dt is None or self._ubar is None:
            raise RuntimeError("run_experiment() deve ser chamado antes de run_control().")
        dt = self._dt
        ubar = self._ubar
        setpoint = np.asarray(setpoint, dtype=float)
        n_steps = int(round(duration_s / dt)) if duration_s > 0 else None

        t_log: list[float] = []
        y_log: list[np.ndarray] = []
        u_log: list[np.ndarray] = []
        t, k = 0.0, 0
        try:
            while n_steps is None or k < n_steps:
                y = self.x.copy()
                u_abs = ubar + K @ (y - setpoint)
                _, u_applied = self._step(u_abs)
                t_log.append(t)
                y_log.append(y)
                u_log.append(u_applied)
                t += dt
                k += 1
        except KeyboardInterrupt:
            if self.verbose:
                print("\n    Controle simulado interrompido pelo usuario.")

        y_arr = np.array(y_log).T if y_log else np.zeros((self.n, 0))
        u_arr = np.array(u_log).T if u_log else np.zeros((self.m, 0))
        return t_log, y_arr, u_arr

    def close(self) -> None:
        pass
