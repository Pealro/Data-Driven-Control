"""Matriz Z multiporta do par de planos (modelo de cavidade).

Generaliza analytic.cavity.impedance para N portas: Z[k, i, j] é a
impedância de transferência entre as portas i e j na frequência f[k].
Mesma série modal validada no caso 1; os fatores modais de cada porta
são pré-computados uma vez por modo (custo O(modos * (N^2 + F))).
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analytic.cavity import EPS0, MU0, SIGMA_CU, _port_factor


def z_matrix(f, a, b, d, eps_r, tan_d, ports, port_size=(1e-3, 1e-3),
             sigma=SIGMA_CU, n_modes=30):
    """Z(f) multiporta [ohm] do par de planos a x b x d [m].

    ports: lista de (x, y) [m]; retorna array (len(f), N, N) complexo.
    """
    f = np.asarray(f, dtype=float)
    w = 2.0 * np.pi * f
    n_ports = len(ports)
    px, py = port_size

    eps = EPS0 * eps_r
    delta_s = np.sqrt(2.0 / (w * MU0 * sigma))
    k2 = w**2 * MU0 * eps * (1.0 - 1j * (tan_d + delta_s / d))   # (F,)

    z = np.zeros((len(f), n_ports, n_ports), dtype=complex)
    for m in range(n_modes + 1):
        for n in range(n_modes + 1):
            eps_mn = (1.0 if m == 0 else 2.0) * (1.0 if n == 0 else 2.0)
            kmn2 = (m * np.pi / a) ** 2 + (n * np.pi / b) ** 2
            fac = np.array([_port_factor(m, n, x, y, px, py, a, b)
                            for x, y in ports])              # (N,)
            coupling = eps_mn * np.outer(fac, fac)            # (N, N)
            z += (1.0 / (kmn2 - k2))[:, None, None] * coupling[None, :, :]
    return (1j * w * MU0 * d / (a * b))[:, None, None] * z
