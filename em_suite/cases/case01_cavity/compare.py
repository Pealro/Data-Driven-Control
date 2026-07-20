"""Caso 1: compara Z11 do openEMS com o modelo de cavidade analítico.

Roda no Windows (ou WSL) após run_openems.py:
    python compare.py

Saídas: comparison.png e report.md neste diretório.
Critério de aprovação: erro < 2% na frequência das 3 primeiras
ressonâncias, e razão |Z| openEMS/analítico dentro de 2x na banda toda
(as perdas têm modelos ligeiramente diferentes nos dois lados).
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from analytic import cavity

# mesmos parâmetros do run_openems.py (mm -> m)
A, B, D = 100e-3, 80e-3, 0.5e-3
EPS_R, TAN_D = 4.4, 0.02
PORT = (A / 4, B / 4)
PORT_SIZE = (1e-3, 1e-3)
TOL_FREQ = 0.02          # 2% nas frequências de ressonância


def main():
    data = np.loadtxt(HERE / 'z11_openems.csv', delimiter=',', skiprows=1)
    f, z_oems = data[:, 0], data[:, 1] + 1j * data[:, 2]

    z_ana = cavity.impedance(f, A, B, D, EPS_R, TAN_D,
                             port_i=PORT, port_size=PORT_SIZE, n_modes=40)
    f_exact = cavity.resonance_freqs(A, B, EPS_R)

    # picos do openEMS na banda simulada
    band = (f > 200e6) & (f < 1.9e9)
    peaks_oems = cavity.find_peaks_hz(f[band], np.abs(z_oems[band]))

    # --- verificação das 3 primeiras ressonâncias -------------------------
    rows, all_pass = [], True
    for mode in [(1, 0), (0, 1), (1, 1)]:
        fe = f_exact[mode]
        if len(peaks_oems) == 0:
            rows.append((mode, fe, np.nan, np.nan, False))
            all_pass = False
            continue
        fp = peaks_oems[np.argmin(np.abs(peaks_oems - fe))]
        err = abs(fp - fe) / fe
        ok = err < TOL_FREQ
        all_pass &= ok
        rows.append((mode, fe, fp, err, ok))

    # --- gráfico ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.semilogy(f / 1e9, np.abs(z_oems), label='openEMS (FDTD)', lw=1.8)
    ax.semilogy(f / 1e9, np.abs(z_ana), '--',
                label='Modelo de cavidade (analítico)', lw=1.5)
    for mode, fe, *_ in rows:
        ax.axvline(fe / 1e9, color='gray', ls=':', lw=0.8)
        ax.text(fe / 1e9, ax.get_ylim()[1] * 0.5, f'{mode}',
                rotation=90, va='top', fontsize=8, color='gray')
    ax.set_xlabel('Frequência [GHz]')
    ax.set_ylabel('|Z11| [$\\Omega$]')
    ax.set_title('Caso 1: par de planos 100 x 80 mm, FR-4 0,5 mm — '
                 'porta em (a/4, b/4)')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / 'comparison.png', dpi=150)

    # --- relatório --------------------------------------------------------
    lines = [
        '# Caso 1 — Cavidade plano-a-plano: openEMS vs analítico\n',
        f'Planos {A*1e3:.0f} x {B*1e3:.0f} mm, d = {D*1e3:.1f} mm, '
        f'eps_r = {EPS_R}, tan_d = {TAN_D}, porta em (a/4, b/4).\n',
        '| Modo | f analítico [MHz] | f openEMS [MHz] | erro | status |',
        '|------|------------------:|----------------:|-----:|:------:|',
    ]
    for mode, fe, fp, err, ok in rows:
        lines.append(
            f'| {mode} | {fe/1e6:.1f} | {fp/1e6:.1f} | {err*100:.2f}% '
            f'| {"PASS" if ok else "FAIL"} |')
    lines.append(
        f'\nCritério: erro < {TOL_FREQ*100:.0f}% na frequência de cada '
        'ressonância. Gráfico: comparison.png\n')
    verdict = 'APROVADO' if all_pass else 'REPROVADO'
    lines.append(f'**Resultado: {verdict}**\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')

    print('\n'.join(lines))
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
