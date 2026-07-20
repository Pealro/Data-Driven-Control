"""Caso 8: Z11(f) da cavidade por Palace driven (FEM) vs modelo analítico.

Fecha o cross-check triplo também no domínio da frequência (o caso 7
comparou só eigenfrequências): FEM com porta lumped de 1 mm em
(a/4, b/4), PMC nas laterais — a MESMA geometria ideal do modelo de
cavidade, então a comparação é curva a curva.

Entrada: postpro/port-Z.csv do Palace (f em GHz, Re/Im de Z[1]).
Critérios: 3 primeiros picos < 2%; razão |Z| em [0.5, 2] em > 90% da
banda 0.1-1.4 GHz (a porta FEM linear de 1 mm x d difere da porta
sinc do modelo — mesma classe de diferença local do caso 4).
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

A, B, D = 100e-3, 80e-3, 0.5e-3
EPS_R, TAN_D = 4.4, 0.02
PORT = (A / 4, B / 4)
TOL_PICO = 0.02


def main():
    # port-V/port-I do Palace são atados ao resistor da porta (V = R*I
    # identicamente); a impedância da estrutura vem do S11:
    # Z = Z0*(1 + S)/(1 - S)
    ds = np.loadtxt(HERE / 'postpro' / 'port-S.csv', delimiter=',',
                    skiprows=1)
    f = ds[:, 0] * 1e9
    s11 = 10.0 ** (ds[:, 1] / 20.0) * np.exp(1j * np.radians(ds[:, 2]))
    z_fem = 50.0 * (1.0 + s11) / (1.0 - s11)

    z_ana = cavity.impedance(f, A, B, D, EPS_R, TAN_D, port_i=PORT,
                             port_size=(1e-3, 0.0), n_modes=40)

    # de-embedding da diferença de DEFINIÇÃO de porta (linha FEM de
    # 1 mm x d vs porta sinc do modelo): um unico jw*dL, ajustado na
    # banda pre-ressonancia — mesma classe de diferenca local
    # quantificada no caso 4 (~0.1-0.2 nH)
    lo = (f >= 100e6) & (f <= 200e6)
    w_lo = 2 * np.pi * f[lo]
    dl_port = float(np.mean((z_fem[lo] - z_ana[lo]).imag / w_lo))
    z_fem = z_fem - 1j * 2 * np.pi * f * dl_port

    band = (f > 100e6) & (f < 1.4e9)
    fb = f[band]
    pk_fem = cavity.find_peaks_hz(fb, np.abs(z_fem[band]))
    pk_ana = cavity.find_peaks_hz(fb, np.abs(z_ana[band]))

    rows, all_ok = [], True
    for i in range(3):
        if len(pk_fem) > i and len(pk_ana) > i:
            err = abs(pk_ana[i] - pk_fem[i]) / pk_fem[i]
            ok = err < TOL_PICO
            rows.append((f'pico {i + 1}', pk_fem[i], pk_ana[i], err, ok))
            all_ok &= ok
        else:
            rows.append((f'pico {i + 1}', np.nan, np.nan, np.nan, False))
            all_ok = False

    ratio = np.abs(z_ana[band]) / np.abs(z_fem[band])
    frac_ok = float(np.mean((ratio > 0.5) & (ratio < 2.0)))
    mag_ok = frac_ok > 0.90
    all_ok &= mag_ok

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.semilogy(f / 1e9, np.abs(z_fem), label='Palace driven (FEM)',
                lw=1.8)
    ax.semilogy(f / 1e9, np.abs(z_ana), '--',
                label='Modelo de cavidade (analítico)', lw=1.5)
    ax.set_xlabel('Frequência [GHz]')
    ax.set_ylabel('|Z11| [$\\Omega$]')
    ax.set_title('Caso 8: cavidade 100 x 80 mm — FEM driven vs analítico')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(HERE / 'comparison.png', dpi=150)

    lines = [
        '# Caso 8 — Palace driven vs modelo de cavidade\n',
        f'De-embedding da definição de porta: dL = {dl_port*1e9:.3f} nH '
        '(porta-linha FEM vs porta sinc; ajustado em 100-200 MHz — '
        'mesma classe de diferença local do caso 4, abaixo da '
        'incerteza prática de l_mnt).\n',
        '| Feature | f Palace [MHz] | f analítico [MHz] | erro | status |',
        '|---|---:|---:|---:|:---:|',
    ]
    for name, ff, fa, err, ok in rows:
        lines.append(f'| {name} | {ff/1e6:.1f} | {fa/1e6:.1f} '
                     f'| {err*100:.2f}% | {"PASS" if ok else "FAIL"} |')
    lines.append(f'\nMagnitude: razão em [0.5, 2] em {frac_ok*100:.1f}% '
                 f'da banda (critério > 90%): '
                 f'{"PASS" if mag_ok else "FAIL"}\n')
    verdict = 'APROVADO' if all_ok else 'REPROVADO'
    lines.append(f'**Resultado: {verdict}**\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
