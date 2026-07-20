"""Caso 2: compara Z0 da microstrip (openEMS) com Hammerstad-Jensen.

Roda após run_openems.py:  python compare.py
Saídas: comparison.png e report.md.
Critério: |Re{Z0} médio na banda 0.5-1.5 GHz - Z0_HJ| / Z0_HJ < 3%
(H-J é quase-estático; avalia-se na parte baixa da banda, onde a
dispersão da microstrip ainda é pequena).
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from analytic import microstrip

W, H, EPS_R = 2.0, 1.0, 4.4
U = W / H
TOL = 0.03


def main():
    data = np.loadtxt(HERE / 'z0_openems.csv', delimiter=',', skiprows=1)
    f, z0 = data[:, 0], data[:, 1] + 1j * data[:, 2]

    z0_hj = float(microstrip.z0(U, EPS_R))
    band = (f >= 0.5e9) & (f <= 1.5e9)
    z0_sim = float(np.mean(z0.real[band]))
    err = abs(z0_sim - z0_hj) / z0_hj
    ok = err < TOL

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(f / 1e9, z0.real, label='openEMS: Re{U/I} (onda viajante)')
    ax.axhline(z0_hj, color='C1', ls='--',
               label=f'Hammerstad-Jensen: {z0_hj:.1f} $\\Omega$')
    ax.axvspan(0.5, 1.5, alpha=0.1, color='gray', label='banda de avaliação')
    ax.set_xlabel('Frequência [GHz]')
    ax.set_ylabel('Z0 [$\\Omega$]')
    ax.set_title(f'Caso 2: microstrip w = {W} mm, h = {H} mm, '
                 f'eps_r = {EPS_R} (u = {U:.1f})')
    ax.set_ylim(z0_hj * 0.8, z0_hj * 1.2)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / 'comparison.png', dpi=150)

    verdict = 'APROVADO' if ok else 'REPROVADO'
    report = (
        '# Caso 2 — Microstrip Z0: openEMS vs Hammerstad-Jensen\n\n'
        f'w = {W} mm, h = {H} mm, eps_r = {EPS_R} (u = {U:.1f}, t = 0).\n\n'
        f'| Grandeza | Valor |\n|---|---:|\n'
        f'| Z0 Hammerstad-Jensen | {z0_hj:.2f} ohm |\n'
        f'| Z0 openEMS (média 0.5-1.5 GHz) | {z0_sim:.2f} ohm |\n'
        f'| erro | {err*100:.2f}% |\n\n'
        f'Critério: erro < {TOL*100:.0f}%. **Resultado: {verdict}**\n')
    (HERE / 'report.md').write_text(report, encoding='utf-8')
    print(report)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
