"""Redução de rede: cargas shunt nas portas da matriz Z.

Particiona as portas em observadas (K) e carregadas (L). Com cargas de
impedância Z_load conectadas em shunt nas portas L, a matriz Z vista
das portas K é o complemento de Schur:

    Z_K = Z_KK - Z_KL @ inv(Z_LL + diag(Z_load)) @ Z_LK

(derivação padrão: V_L = -Z_load * I_L na convenção de corrente
entrando na rede).
"""

import numpy as np


def reduce_loaded(z, keep_idx, load_idx, z_loads):
    """Reduz a matriz Z (F, N, N) com cargas shunt.

    keep_idx: índices das portas observadas; load_idx: portas com carga;
    z_loads: array (F, len(load_idx)) com a impedância de cada carga.
    Retorna (F, K, K).
    """
    z = np.asarray(z)
    keep_idx = list(keep_idx)
    load_idx = list(load_idx)
    if not load_idx:
        return z[:, keep_idx][:, :, keep_idx]

    z_kk = z[:, keep_idx][:, :, keep_idx]
    z_kl = z[:, keep_idx][:, :, load_idx]
    z_lk = z[:, load_idx][:, :, keep_idx]
    z_ll = z[:, load_idx][:, :, load_idx]

    nl = len(load_idx)
    diag = np.zeros_like(z_ll)
    diag[:, np.arange(nl), np.arange(nl)] = np.asarray(z_loads)
    inner = np.linalg.solve(z_ll + diag, z_lk)
    return z_kk - z_kl @ inner


def z_in(f, z, chip_port, decaps_at):
    """Impedância de entrada Zin(f) na porta do chip com decaps montados.

    f: frequências [Hz]; z: matriz Z (F, N, N); chip_port: índice da
    porta do chip; decaps_at: dict {índice_da_porta: Decap}.
    Retorna array (F,) complexo.
    """
    load_idx = sorted(decaps_at)
    if chip_port in load_idx:
        raise ValueError('decap na mesma porta do chip: use portas distintas')
    if not load_idx:
        return z[:, chip_port, chip_port]
    z_loads = np.stack([decaps_at[i].z(f) for i in load_idx], axis=1)
    zr = reduce_loaded(z, [chip_port], load_idx, z_loads)
    return zr[:, 0, 0]
