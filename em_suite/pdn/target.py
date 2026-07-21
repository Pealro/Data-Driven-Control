"""Impedância-alvo (target impedance) do rail.

Regra clássica (Smith/Bogatin): Z_t = dV_permitido / dI_transiente,
plana na banda em que o chip demanda corrente. dV = ripple permitido
(fração da tensão do rail); dI = degrau de corrente do pior caso
(para modem GSM: burst TX de ~2 A com bordas rápidas).

Acima do "joelho" (frequência máxima de conteúdo espectral relevante,
f_knee ~ 0.35/t_rise), o pacote/die filtram e o requisito relaxa;
modela-se opcionalmente Z_t subindo +20 dB/dec acima de f_knee.
"""

import numpy as np


def target_z(v_rail, ripple_frac, di_step):
    """Z_t plano [ohm]: (v_rail * ripple_frac) / di_step."""
    return v_rail * ripple_frac / di_step


def target_profile(f, v_rail, ripple_frac, di_step, f_knee=None):
    """Perfil Z_t(f): plano até f_knee, +20 dB/dec acima (se f_knee dado)."""
    zt = np.full_like(np.asarray(f, dtype=float),
                      target_z(v_rail, ripple_frac, di_step))
    if f_knee is not None:
        f = np.asarray(f, dtype=float)
        acima = f > f_knee
        zt[acima] *= f[acima] / f_knee
    return zt


def violations(f, z_mag, zt):
    """Sub-bandas onde |Z| > Z_t: lista de (f_ini, f_fim, pior_razão)."""
    bad = np.asarray(z_mag) > np.asarray(zt)
    out, start = [], None
    for i, b in enumerate(bad):
        if b and start is None:
            start = i
        elif not b and start is not None:
            seg = slice(start, i)
            out.append((f[start], f[i - 1],
                        float(np.max(z_mag[seg] / zt[seg]))))
            start = None
    if start is not None:
        seg = slice(start, len(bad))
        out.append((f[start], f[-1], float(np.max(z_mag[seg] / zt[seg]))))
    return out
