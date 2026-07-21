"""Caso 1: par de planos 100 x 80 mm, FR-4 0.5 mm — Z11 via openEMS (FDTD).

Roda no WSL (venv com openEMS compilado):
    source ~/venv-em/bin/activate && python run_openems.py

Saída: z11_openems.csv (f_Hz, ReZ, ImZ) no diretório deste script.
Os dumps de campo do FDTD vão para um diretório temporário local do WSL
(evita I/O lento no /mnt/c).
"""

import os
import tempfile
import numpy as np

from CSXCAD import ContinuousStructure
from openEMS import openEMS

# --- geometria e material (mesmos parâmetros do modelo analítico) ---------
A, B = 100.0, 80.0        # mm, dimensões laterais dos planos
D = 0.5                   # mm, separação (dielétrico)
EPS_R, TAN_D = 4.4, 0.02
PORT_X, PORT_Y = A / 4.0, B / 4.0   # porta em (a/4, b/4)
PORT_W = 1.0              # mm, lado da região da porta lumped

F0, FC = 1.0e9, 1.0e9     # excitação gaussiana: 0 a 2 GHz
UNIT = 1e-3               # unidade da malha: mm

EPS0 = 8.8541878128e-12
KAPPA = 2 * np.pi * F0 * EPS0 * EPS_R * TAN_D  # condutividade eq. em f0


def main():
    fdtd = openEMS(NrTS=300_000, EndCriteria=1e-4)
    fdtd.SetGaussExcite(F0, FC)
    fdtd.SetBoundaryCond(['MUR'] * 6)

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(UNIT)

    # dielétrico entre os planos
    fr4 = csx.AddMaterial('FR4', epsilon=EPS_R, kappa=KAPPA)
    fr4.AddBox(priority=1, start=[0, 0, 0], stop=[A, B, D])

    # planos de cobre como PEC (folhas em z = 0 e z = D)
    pec = csx.AddMetal('planes')
    pec.AddBox(priority=10, start=[0, 0, 0], stop=[A, B, 0])
    pec.AddBox(priority=10, start=[0, 0, D], stop=[A, B, D])

    # porta lumped vertical entre os planos
    p0 = [PORT_X - PORT_W / 2, PORT_Y - PORT_W / 2, 0]
    p1 = [PORT_X + PORT_W / 2, PORT_Y + PORT_W / 2, D]
    port = fdtd.AddLumpedPort(1, 50.0, p0, p1, 'z', excite=1.0)

    # --- malha ------------------------------------------------------------
    margin = 20.0  # mm de ar em volta (fringing das bordas abertas)
    lam_min_mm = 3e8 / (np.sqrt(EPS_R) * (F0 + FC)) / UNIT  # ~35.7 mm
    res_lat = lam_min_mm / 20.0

    x = np.concatenate([
        np.array([-margin, 0, A, A + margin]),
        np.arange(0, A + res_lat, res_lat),
        np.array([p0[0], PORT_X, p1[0]]),
    ])
    y = np.concatenate([
        np.array([-margin, 0, B, B + margin]),
        np.arange(0, B + res_lat, res_lat),
        np.array([p0[1], PORT_Y, p1[1]]),
    ])
    z = np.concatenate([
        np.array([-margin, 0, D, D + margin]),
        np.linspace(0, D, 5),          # >= 4 células no gap
    ])
    mesh.AddLine('x', np.unique(x))
    mesh.AddLine('y', np.unique(y))
    mesh.AddLine('z', np.unique(z))
    mesh.SmoothMeshLines('all', res_lat, 1.4)

    # --- executa ----------------------------------------------------------
    sim_path = os.path.join(tempfile.gettempdir(), 'case01_cavity')
    fdtd.Run(sim_path, cleanup=True)

    # --- pós-processa: Z11 = U/I na porta ---------------------------------
    f = np.linspace(50e6, 2.0e9, 2001)
    port.CalcPort(sim_path, f)
    z11 = port.uf_tot / port.if_tot

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'z11_openems.csv')
    np.savetxt(out,
               np.column_stack([f, z11.real, z11.imag]),
               delimiter=',', header='f_Hz,ReZ_ohm,ImZ_ohm', comments='')
    print(f'OK: {out} ({len(f)} pontos)')


if __name__ == '__main__':
    main()
