# -*- coding: utf-8 -*-
"""Oscilador de Van der Pol forcado -- planta NAO-linear simulada, alvo natural
do controle com modelo de Koopman (reproduz o exemplo do artigo Strasser et al.
dentro do projeto, sem hardware).

    x1_dot = x2
    x2_dot = mu (1 - x1^2) x2 - x1 + u        (entrada escalar, m=1)

Implementa a interface Plant (plants/base.py):
- run_experiment: coleta uma trajetoria com entrada aleatoria (dados p/ o EDMD);
- run_control_external: malha fechada aplicando u = compute_u(x) a cada passo --
  usado tanto pela busca de controladores (koopman/search) quanto pelo teste
  final. NAO usa a lei linear u=ubar+K(y-sp) (Van der Pol nao e linear); o
  compute_u vem do KoopmanRationalController.

O equilibrio de regulacao e a ORIGEM (0,0) -- ponto fixo instavel do VdP nao
forcado, que o controlador de Koopman estabiliza. Por isso run_experiment
devolve ybar=[0,0] (alvo), nao a media dos dados (que ficam no ciclo limite)."""

import time

import numpy as np

from plants.base import Plant


def vanderpol_derivative(x, u, mu):
    x1, x2 = float(x[0]), float(x[1])
    return np.array([x2, mu * (1.0 - x1 * x1) * x2 - x1 + float(u)], dtype=float)


def euler_step(x, u, dt, mu):
    return np.asarray(x, dtype=float).reshape(2,) + dt * vanderpol_derivative(x, u, mu)


class VanDerPolPlant(Plant):
    n = 2
    m = 1

    def __init__(
        self,
        mu: float = 1.0,
        x0_data=(-0.128, -0.948),
        x0_control=(1.0, -0.6),
        real_time: bool = False,
        verbose: bool = True,
    ):
        self.mu = float(mu)
        self.x0_data = np.asarray(x0_data, dtype=float)
        self.x0_control = np.asarray(x0_control, dtype=float)
        self.real_time = real_time
        self.verbose = verbose
        self.x = self.x0_data.copy()
        self._dt = None

    # ------------------------------------------------------------------ dados
    def run_experiment(
        self, T, dt, ubar, settle_duration_s, excitation_amplitude, seed, on_sample=None
    ):
        """Coleta T+1 amostras a partir de x0_data com entrada aleatoria
        U(-excitation_amplitude, +excitation_amplitude). ubar/settle sao
        ignorados (VdP nao tem equilibrio estavel p/ assentar); o alvo de
        regulacao e a origem, entao ybar=[0,0]."""
        self._dt = dt
        rng = np.random.default_rng(seed)
        u_seq = rng.uniform(-excitation_amplitude, excitation_amplitude, size=T)

        t_raw = np.arange(T + 1) * dt
        y_raw = np.zeros((self.n, T + 1))
        u_raw = np.zeros((self.m, T))
        self.x = self.x0_data.copy()
        y_raw[:, 0] = self.x
        if on_sample:
            on_sample(t_raw[0], self.x.tolist(), [0.0])
        for k in range(T):
            if self.real_time:
                time.sleep(dt)
            self.x = euler_step(self.x, u_seq[k], dt, self.mu)
            y_raw[:, k + 1] = self.x
            u_raw[0, k] = u_seq[k]
            if on_sample:
                on_sample(t_raw[k + 1], self.x.tolist(), [float(u_seq[k])])

        ybar = np.zeros(self.n)  # alvo de regulacao = origem
        if self.verbose:
            print(f"    Van der Pol: {T} amostras coletadas, alvo de regulacao ybar = {ybar}")
        return ybar, t_raw, y_raw, u_raw

    # --------------------------------------------------------------- controle
    def rollout(self, compute_u, x0, n_steps, dt, on_sample=None, should_abort=None):
        """Malha fechada u=compute_u(x) sobre a dinamica real, com guardas de
        explosao (mesma convencao do notebook). Retorna dict com X, U, t,
        explodiu, motivo. Reusado pela busca e pelo controle final."""
        X = np.zeros((n_steps + 1, 2))
        U = np.zeros(n_steps)
        t = np.arange(n_steps + 1) * dt
        X[0, :] = np.asarray(x0, dtype=float)
        explodiu, motivo = False, "ok"
        for k in range(n_steps):
            if self.real_time:
                time.sleep(dt)
            try:
                u = compute_u(X[k, :])
            except Exception as erro:
                X[k + 1:, :] = np.nan
                U[k:] = np.nan
                explodiu, motivo = True, str(erro)
                break
            x_next = euler_step(X[k, :], u, dt, self.mu)
            if not np.all(np.isfinite(x_next)) or np.linalg.norm(x_next) > 1e8:
                X[k + 1:, :] = np.nan
                U[k:] = np.nan
                explodiu, motivo = True, "estado explodiu"
                break
            X[k + 1, :] = x_next
            U[k] = u
            if on_sample:
                on_sample(t[k + 1], x_next.tolist(), [float(u)])
            if should_abort and should_abort():
                X = X[:k + 2]
                U = U[:k + 1]
                t = t[:k + 2]
                break
        return {"X": X, "U": U, "t": t, "explodiu": explodiu, "motivo": motivo}

    def run_control_external(self, compute_u, duration_s, x0=None, on_sample=None, should_abort=None):
        """Interface de controle por callback (u = compute_u(x)) -- o que o ramo
        Koopman do runner chama. duration_s=0 usa T_sim padrao de 20s.
        Retorna (t_log, y_log (n,N), u_log (m,N))."""
        if self._dt is None:
            raise RuntimeError("run_experiment() deve ser chamado antes do controle.")
        dt = self._dt
        x0 = self.x0_control if x0 is None else np.asarray(x0, dtype=float)
        n_steps = int(round((duration_s if duration_s > 0 else 20.0) / dt))
        sim = self.rollout(compute_u, x0, n_steps, dt, on_sample=on_sample, should_abort=should_abort)
        X, U, t = sim["X"], sim["U"], sim["t"]
        finit = np.all(np.isfinite(X), axis=1)
        n_finite = int(np.sum(finit))
        # t_log/y_log/u_log com o MESMO comprimento (n de passos de controle
        # completos): y[k] e o estado ANTES de aplicar u[k], convencao de
        # save_control_test_csv. O estado terminal (sem input) fica so no plot.
        n_ctrl = max(n_finite - 1, 0)
        y_log = X[:n_ctrl].T
        u_log = U[:n_ctrl].reshape(1, -1)
        t_log = list(t[:n_ctrl])
        if self.verbose:
            print(f"    Van der Pol malha fechada: explodiu={sim['explodiu']} ({sim['motivo']})")
        return t_log, y_log, u_log

    def run_control(self, K, setpoint, duration_s, on_sample=None, should_abort=None):
        raise NotImplementedError(
            "VanDerPolPlant usa run_control_external(compute_u, ...) (controle "
            "racional de Koopman), nao a lei linear u=ubar+K(y-setpoint)."
        )

    def close(self):
        pass
