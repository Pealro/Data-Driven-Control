"""Extrator de matriz Z multiporta de par de planos via openEMS (FDTD).

Generaliza o método do caso 4 para N portas e geometria de plano
arbitrária (fendas/recortes no plano superior, "PWR"): roda N
simulações — em cada uma, excita uma porta (50 ohm) e sonda as demais
(1 Mohm, i ~ 0) — e monta Z coluna a coluna:

    Z[:, j] = u_j / i_k   com a porta k excitada

É o caminho para geometria real de placa, onde o modelo de cavidade
retangular (pdn.planes) deixa de valer.

USO (dentro do WSL, venv com openEMS):
    python extract_openems.py config.json

config.json:
{
  "a": 100.0, "b": 80.0, "d": 0.5,            // mm
  "eps_r": 4.4, "tan_d": 0.02,
  "ports": [[25.0, 20.0], [75.0, 40.0]],      // mm
  "slots": [[48.0, 20.0, 52.0, 80.0]],        // fendas no plano PWR
  "f_start": 30e6, "f_stop": 1.5e9, "n_f": 2001,
  "nrts": 400000, "out": "zmat.csv"
}

Saída: CSV com colunas f_Hz, ReZ11, ImZ11, ReZ21, ImZ21, ... (ordem
column-major: todas as linhas i da coluna j = excitação j).
"""

import json
import os
import sys
import tempfile
import numpy as np

from CSXCAD import ContinuousStructure
from openEMS import openEMS

PORT_W = 1.0     # mm, lado das portas lumped
R_PROBE = 1e6
F0, FC = 1.0e9, 1.0e9
UNIT = 1e-3
EPS0 = 8.8541878128e-12


def _top_plane_polygon(a, b, slots):
    """Poligono do plano superior com fendas retangulares subtraidas.

    Suporta fendas que tocam a borda y = b (caso split tipico). Para
    fendas internas seria preciso poligono com furo — fora do escopo.
    """
    if not slots:
        return [(0, 0), (a, 0), (a, b), (0, b)]
    pts = [(0.0, 0.0), (a, 0.0), (a, b)]
    # percorre a borda superior da direita para a esquerda descendo em
    # cada fenda que toca y = b
    for x0, y0, x1, y1 in sorted(slots, key=lambda s: -s[0]):
        if abs(y1 - b) > 1e-9:
            raise ValueError('fenda deve tocar a borda y = b '
                             '(split a partir da borda)')
        pts += [(x1, b), (x1, y0), (x0, y0), (x0, b)]
    pts.append((0.0, b))
    return pts


def build_and_run(cfg, excite_port, sim_tag, f_out):
    a, b, d = cfg['a'], cfg['b'], cfg['d']
    eps_r, tan_d = cfg['eps_r'], cfg['tan_d']
    ports_xy = cfg['ports']
    slots = cfg.get('slots', [])

    fdtd = openEMS(NrTS=int(cfg.get('nrts', 400_000)), EndCriteria=1e-4)
    fdtd.SetGaussExcite(F0, FC)
    fdtd.SetBoundaryCond(['MUR'] * 6)

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(UNIT)

    kappa = 2 * np.pi * F0 * EPS0 * eps_r * tan_d
    fr4 = csx.AddMaterial('FR4', epsilon=eps_r, kappa=kappa)
    fr4.AddBox(priority=1, start=[0, 0, 0], stop=[a, b, d])

    pec = csx.AddMetal('planes')
    pec.AddBox(priority=10, start=[0, 0, 0], stop=[a, b, 0])  # GND intacto
    poly = _top_plane_polygon(a, b, slots)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    prim = pec.AddLinPoly(priority=10, points=[xs, ys],
                          norm_dir='z', elevation=d, length=0)

    ports = []
    for k, (px, py) in enumerate(ports_xy, start=1):
        p0 = [px - PORT_W / 2, py - PORT_W / 2, 0]
        p1 = [px + PORT_W / 2, py + PORT_W / 2, d]
        if k == excite_port:
            ports.append(fdtd.AddLumpedPort(k, 50.0, p0, p1, 'z',
                                            excite=1.0))
        else:
            ports.append(fdtd.AddLumpedPort(k, R_PROBE, p0, p1, 'z',
                                            excite=0.0))

    margin = 20.0
    lam_min_mm = 3e8 / (np.sqrt(eps_r) * (F0 + FC)) / UNIT
    res_lat = lam_min_mm / 20.0

    xl = [-margin, 0, a, a + margin]
    yl = [-margin, 0, b, b + margin]
    for px, py in ports_xy:
        xl += [px - PORT_W / 2, px, px + PORT_W / 2]
        yl += [py - PORT_W / 2, py, py + PORT_W / 2]
    for x0, y0, x1, y1 in slots:
        # linhas nas bordas da fenda (regra dos tercos simplificada:
        # linha na borda + linha fina dentro e fora)
        fine = res_lat / 4.0
        xl += [x0 - fine, x0, x0 + fine, x1 - fine, x1, x1 + fine]
        yl += [y0 - fine, y0, y0 + fine]
    x = np.concatenate([np.array(xl), np.arange(0, a + res_lat, res_lat)])
    y = np.concatenate([np.array(yl), np.arange(0, b + res_lat, res_lat)])
    z = np.concatenate([np.array([-margin, 0, d, d + margin]),
                        np.linspace(0, d, 5)])
    mesh.AddLine('x', np.unique(x))
    mesh.AddLine('y', np.unique(y))
    mesh.AddLine('z', np.unique(z))
    mesh.SmoothMeshLines('all', res_lat, 1.4)

    sim_path = os.path.join(tempfile.gettempdir(), f'zextract_{sim_tag}')
    fdtd.Run(sim_path, cleanup=True)

    for p in ports:
        p.CalcPort(sim_path, f_out)
    return ports


def main(cfg_path):
    # resolve JA o caminho absoluto: fdtd.Run() muda o cwd do processo,
    # o que quebraria a resolucao de caminhos relativos depois das sims
    cfg_path = os.path.abspath(cfg_path)
    with open(cfg_path) as fh:
        cfg = json.load(fh)
    n = len(cfg['ports'])
    f = np.linspace(cfg['f_start'], cfg['f_stop'], int(cfg['n_f']))

    z = np.empty((len(f), n, n), dtype=complex)
    for j in range(1, n + 1):
        ports = build_and_run(cfg, j, f'exc{j}', f)
        i_exc = ports[j - 1].if_tot
        for i in range(n):
            z[:, i, j - 1] = ports[i].uf_tot / i_exc

    cols, header = [f], ['f_Hz']
    for j in range(n):
        for i in range(n):
            cols += [z[:, i, j].real, z[:, i, j].imag]
            header += [f'ReZ{i + 1}{j + 1}', f'ImZ{i + 1}{j + 1}']
    out = cfg.get('out', 'zmat.csv')
    if not os.path.isabs(out):
        out = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), out)
    np.savetxt(out, np.column_stack(cols), delimiter=',',
               header=','.join(header), comments='')
    print(f'OK: {out}')


if __name__ == '__main__':
    main(sys.argv[1])
