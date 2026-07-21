"""Caso 2: microstrip w = 2 mm, h = 1 mm, eps_r = 4.4 — Z0 via openEMS.

Linha casada (termina no PML), porta MSL com plano de medição no meio:
Z0(f) = U/I da onda viajante. Alvo: Hammerstad-Jensen Z0(u=2, 4.4) = 48.7 ohm.

Roda no WSL: source ~/venv-em/bin/activate && python run_openems.py
Saída: z0_openems.csv (f_Hz, ReZ0, ImZ0) neste diretório.
"""

import os
import tempfile
import numpy as np

from CSXCAD import ContinuousStructure
from openEMS import openEMS

W, H = 2.0, 1.0            # mm: largura da trilha, altura do substrato
EPS_R = 4.4                # sem perdas: H-J é quase-estático sem perdas
L = 60.0                   # mm: comprimento da linha (atravessa o dominio x)
SUB_W = 40.0               # mm: largura do substrato/dominio em y
AIR_TOP = 15.0             # mm de ar acima
F0, FC = 1.5e9, 1.5e9      # excitação: 0 a 3 GHz
UNIT = 1e-3


def main():
    fdtd = openEMS(NrTS=200_000, EndCriteria=1e-4)
    fdtd.SetGaussExcite(F0, FC)
    # linha corre em x e morre no PML dos dois lados -> onda viajante pura
    fdtd.SetBoundaryCond(['PML_8', 'PML_8', 'MUR', 'MUR', 'PEC', 'MUR'])

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(UNIT)

    sub = csx.AddMaterial('FR4', epsilon=EPS_R)
    sub.AddBox(priority=1, start=[0, -SUB_W / 2, 0], stop=[L, SUB_W / 2, H])

    # trilha (PEC, folha em z = H); o plano de terra é o BC PEC em z = 0
    strip = csx.AddMetal('strip')

    res_fine = W / 12.0
    # malha: regra dos terços nas bordas da trilha (y = +/- W/2)
    # (a malha precisa existir ANTES do AddMSLPort)
    res_coarse = 3e8 / (np.sqrt(EPS_R) * (F0 + FC)) / UNIT / 20.0
    third = res_fine / 3.0
    x = np.arange(0, L + res_fine, res_fine)
    # regra dos tercos do openEMS: linha a res/3 DENTRO do metal e
    # 2*res/3 FORA, em cada borda da trilha
    y = np.concatenate([
        np.array([-SUB_W / 2, SUB_W / 2, 0]),
        np.array([-W / 2 - 2 * third, -W / 2 + third,
                  W / 2 - third, W / 2 + 2 * third]),
        np.arange(-W / 2 + third, W / 2 - third / 2, res_fine),
    ])
    z = np.concatenate([
        np.linspace(0, H, 9),
        np.array([H + AIR_TOP]),
        H + np.array([res_fine, 2 * res_fine, 4 * res_fine]),
    ])
    mesh.AddLine('x', np.unique(x))
    mesh.AddLine('y', np.unique(y))
    mesh.AddLine('z', np.unique(z))
    mesh.SmoothMeshLines('all', res_coarse, 1.4)

    # o box da porta atravessa da trilha (z = H) ao terra (z = 0);
    # a propria porta MSL cria a folha metalica da trilha
    port = fdtd.AddMSLPort(1, strip,
                           [0, -W / 2, H], [L, W / 2, 0],
                           'x', 'z', excite=-1,
                           FeedShift=10 * res_fine,
                           MeasPlaneShift=L / 2,
                           priority=10)

    sim_path = os.path.join(tempfile.gettempdir(), 'case02_msl')
    fdtd.Run(sim_path, cleanup=True)

    f = np.linspace(0.2e9, 3.0e9, 1401)
    port.CalcPort(sim_path, f)
    z0 = port.uf_tot / port.if_tot

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'z0_openems.csv')
    np.savetxt(out, np.column_stack([f, z0.real, z0.imag]),
               delimiter=',', header='f_Hz,ReZ0_ohm,ImZ0_ohm', comments='')
    print(f'OK: {out}')


if __name__ == '__main__':
    main()
