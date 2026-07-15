# -*- coding: utf-8 -*-
"""Controlador racional de Koopman: u = (K z)/(1 - Kw z), com z = Phi(x).

Encapsula K, Kw e os expoentes do lifting num objeto que sabe converter um
estado fisico x direto no comando u -- e o que o laco de controle (simulado ou,
na Fase 2, hardware via URAW) chama a cada passo."""

import numpy as np

from koopman.lifting import phi_vector


class KoopmanRationalController:
    def __init__(self, K, Kw, exponents, denom_tol=1e-12, u_abs_max=1e8):
        self.K = np.asarray(K, dtype=float).reshape(1, -1)
        self.Kw = np.asarray(Kw, dtype=float).reshape(1, -1)
        self.exponents = np.asarray(exponents, dtype=int)
        self.denom_tol = denom_tol
        self.u_abs_max = u_abs_max

    def lift(self, x) -> np.ndarray:
        return phi_vector(x, self.exponents)

    def compute_u(self, x) -> float:
        """u = (Kz)/(1-Kw z). Levanta ZeroDivisionError se o denominador ficar
        singular (a malha saiu da regiao de atracao) -- o chamador trata como
        'explodiu', mesma convencao do notebook (controle_racional_m1)."""
        z = self.lift(x).reshape(-1, 1)
        numer = float((self.K @ z).item())
        denom = float(1.0 - (self.Kw @ z).item())
        if abs(denom) < self.denom_tol:
            raise ZeroDivisionError(f"denominador racional singular: {denom:.3e}")
        u = numer / denom
        if not np.isfinite(u) or abs(u) > self.u_abs_max:
            raise ValueError(f"controle explodiu: u={u}")
        return u
