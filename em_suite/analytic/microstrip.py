"""Microstrip: Z0 e eps_eff por Hammerstad-Jensen (1980).

Referência: E. Hammerstad, O. Jensen, "Accurate Models for Microstrip
Computer-Aided Design", IEEE MTT-S 1980. Precisão declarada: ~0.2% para
eps_eff e ~1% para Z0 na faixa 0.01 <= u <= 100, eps_r <= 128 (t = 0,
quase-estático, sem dispersão).

Notação: u = w/h (largura da trilha / altura do dielétrico).
"""

import numpy as np

ETA0 = 376.730313668  # ohm, impedância do vácuo


def _f_u(u):
    return 6.0 + (2.0 * np.pi - 6.0) * np.exp(-((30.666 / u) ** 0.7528))


def z0_air(u):
    """Z01(u): impedância da microstrip homogênea (ar), eq. de H-J."""
    fu = _f_u(u)
    return ETA0 / (2.0 * np.pi) * np.log(fu / u + np.sqrt(1.0 + (2.0 / u) ** 2))


def eps_eff(u, eps_r):
    """Permissividade efetiva quase-estática de Hammerstad-Jensen."""
    a = (1.0
         + 1.0 / 49.0 * np.log((u**4 + (u / 52.0) ** 2) / (u**4 + 0.432))
         + 1.0 / 18.7 * np.log(1.0 + (u / 18.1) ** 3))
    b = 0.564 * ((eps_r - 0.9) / (eps_r + 3.0)) ** 0.053
    return (eps_r + 1.0) / 2.0 + (eps_r - 1.0) / 2.0 * (1.0 + 10.0 / u) ** (-a * b)


def z0(u, eps_r):
    """Impedância característica Z0 [ohm] da microstrip (t = 0)."""
    return z0_air(u) / np.sqrt(eps_eff(u, eps_r))
