"""Caso 4 (v2): matriz Z 2x2 da cavidade via openEMS — duas simulações.

MUDANÇA DE MÉTODO: a v1 embutia o decap como elemento RLC lumped na
FDTD, mas o elemento série do openEMS (LEtype=1) IGNOROU SetInductance
(verificado: pico de anti-ressonância caiu exatamente na posição
prevista para L=0). Em vez de depender dessa semântica, extraímos a
matriz Z 2x2 dos planos por FDTD e conectamos o capacitor numericamente
— o MESMO modelo RLC e a MESMA redução de Schur nos dois lados. Isso
isola o que o caso valida: o modelo de cavidade multiporta.

Duas simulações: excita porta 1 (chip) com sonda 1 Mohm na porta 2
(cap), e vice-versa. Com a sonda quase aberta, i_sonda ~ 0:
    sim A: Z11 = u1/i1, Z21 = u2/i1
    sim B: Z22 = u2/i2, Z12 = u1/i2

Roda no WSL: source ~/venv-em/bin/activate && python run_openems.py
Saída: zmat_openems.csv (f, Re/Im de Z11, Z21, Z22, Z12).
"""

import os
import tempfile
import numpy as np

from CSXCAD import ContinuousStructure
from openEMS import openEMS

A, B, D = 100.0, 80.0, 0.5
EPS_R, TAN_D = 4.4, 0.02
P1 = (A / 4.0, B / 4.0)          # chip
P2 = (3.0 * A / 4.0, B / 2.0)    # cap
PORT_W = 1.0
R_PROBE = 1e6

F0, FC = 1.0e9, 1.0e9
UNIT = 1e-3
EPS0 = 8.8541878128e-12
KAPPA = 2 * np.pi * F0 * EPS0 * EPS_R * TAN_D

F_OUT = np.linspace(30e6, 1.5e9, 2001)


def build_and_run(excite_port, sim_tag):
    """Monta a cavidade com 2 portas lumped e excita a porta indicada."""
    fdtd = openEMS(NrTS=400_000, EndCriteria=1e-4)
    fdtd.SetGaussExcite(F0, FC)
    fdtd.SetBoundaryCond(['MUR'] * 6)

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(UNIT)

    fr4 = csx.AddMaterial('FR4', epsilon=EPS_R, kappa=KAPPA)
    fr4.AddBox(priority=1, start=[0, 0, 0], stop=[A, B, D])
    pec = csx.AddMetal('planes')
    pec.AddBox(priority=10, start=[0, 0, 0], stop=[A, B, 0])
    pec.AddBox(priority=10, start=[0, 0, D], stop=[A, B, D])

    ports = []
    for k, (px, py) in enumerate([P1, P2], start=1):
        p0 = [px - PORT_W / 2, py - PORT_W / 2, 0]
        p1 = [px + PORT_W / 2, py + PORT_W / 2, D]
        if k == excite_port:
            ports.append(fdtd.AddLumpedPort(k, 50.0, p0, p1, 'z',
                                            excite=1.0))
        else:
            ports.append(fdtd.AddLumpedPort(k, R_PROBE, p0, p1, 'z',
                                            excite=0.0))

    margin = 20.0
    lam_min_mm = 3e8 / (np.sqrt(EPS_R) * (F0 + FC)) / UNIT
    res_lat = lam_min_mm / 20.0
    x = np.concatenate([
        np.array([-margin, 0, A, A + margin]),
        np.arange(0, A + res_lat, res_lat),
        np.array([P1[0] - PORT_W / 2, P1[0], P1[0] + PORT_W / 2,
                  P2[0] - PORT_W / 2, P2[0], P2[0] + PORT_W / 2]),
    ])
    y = np.concatenate([
        np.array([-margin, 0, B, B + margin]),
        np.arange(0, B + res_lat, res_lat),
        np.array([P1[1] - PORT_W / 2, P1[1], P1[1] + PORT_W / 2,
                  P2[1] - PORT_W / 2, P2[1], P2[1] + PORT_W / 2]),
    ])
    z = np.concatenate([
        np.array([-margin, 0, D, D + margin]),
        np.linspace(0, D, 5),
    ])
    mesh.AddLine('x', np.unique(x))
    mesh.AddLine('y', np.unique(y))
    mesh.AddLine('z', np.unique(z))
    mesh.SmoothMeshLines('all', res_lat, 1.4)

    sim_path = os.path.join(tempfile.gettempdir(), f'case04_{sim_tag}')
    fdtd.Run(sim_path, cleanup=True)

    for p in ports:
        p.CalcPort(sim_path, F_OUT)
    return ports


def main():
    # sim A: excita porta 1 -> coluna 1 da matriz Z
    pa = build_and_run(1, 'exc1')
    z11 = pa[0].uf_tot / pa[0].if_tot
    z21 = pa[1].uf_tot / pa[0].if_tot

    # sim B: excita porta 2 -> coluna 2
    pb = build_and_run(2, 'exc2')
    z22 = pb[1].uf_tot / pb[1].if_tot
    z12 = pb[0].uf_tot / pb[1].if_tot

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'zmat_openems.csv')
    np.savetxt(out, np.column_stack([
        F_OUT, z11.real, z11.imag, z21.real, z21.imag,
        z22.real, z22.imag, z12.real, z12.imag]),
        delimiter=',',
        header='f_Hz,ReZ11,ImZ11,ReZ21,ImZ21,ReZ22,ImZ22,ReZ12,ImZ12',
        comments='')
    print(f'OK: {out}')


if __name__ == '__main__':
    main()
