# -*- coding: utf-8 -*-
"""Controlador de estado aumentado (delay-embedding): mantem o historico de y e
u no PC e aplica u = ubar + K (x~ - x~bar), onde x~ e o estado aumentado montado
em tempo real (mesma convencao de build_X0_X1_U0). Como x~ esta em coordenadas
de desvio, o equilibrio e x~=0, entao u = ubar + K x~.

Usado quando o metodo escolhido e delay-embedding (K tem n_eff colunas, nao n):
a lei nao cabe na run_control linear (u=ubar+K(y-setpoint)) porque precisa do
historico. E um callback compute_u(y) que o laco de controle por callback das
plantas (run_control_external) consome. L=1 reduz a u = ubar + K (y - ybar)."""

from collections import deque

import numpy as np


class DelayEmbeddedController:
    def __init__(self, K, ybar, ubar, L: int):
        self.K = np.asarray(K, dtype=float)          # (m, n_eff)
        self.ybar = np.asarray(ybar, dtype=float).reshape(-1)
        self.ubar = np.asarray(ubar, dtype=float).reshape(-1)
        self.L = int(L)
        self.n = self.ybar.size
        self.m = self.ubar.size
        # historico dos L-1 desvios passados de y e u (mais recente a esquerda),
        # inicializado no equilibrio (zeros) -- warm start honesto
        self._dy_hist = deque([np.zeros(self.n) for _ in range(L - 1)], maxlen=L - 1)
        self._du_hist = deque([np.zeros(self.m) for _ in range(L - 1)], maxlen=L - 1)

    def compute_u(self, y):
        dy = np.asarray(y, dtype=float).reshape(-1) - self.ybar
        # x~ = [dy(k), dy(k-1)..dy(k-L+1), du(k-1)..du(k-L+1)]
        x_tilde = np.concatenate([dy, *self._dy_hist, *self._du_hist])
        u = self.ubar + self.K @ x_tilde
        du = u - self.ubar
        if self.L > 1:
            self._dy_hist.appendleft(dy)
            self._du_hist.appendleft(du)
        return u
