"""Caso 4 (v2): pipeline PDN vs matriz Z extraída do openEMS.

Compara em dois níveis:
1. Física dos planos: Z12 (transferência) analítico vs FDTD — estende o
   caso 1 (que validou Z11) para o acoplamento entre portas;
2. Pipeline completo: o MESMO Decap (1 nF / 50 mohm / 1 nH) conectado
   pela MESMA redução de Schur sobre as duas matrizes -> Zin no chip.
   Diferenças aqui vêm só do modelo de planos, não do circuito.

Critérios:
- 2 primeiros picos de Zin: erro < 3%
- dip da SRF: erro < 5% — tolerância maior JUSTIFICADA: f_dip depende da
  indutância série total (~2 nH); a definição da indutância local da
  porta difere ~0.2 nH entre a porta FDTD discretizada (2x2 células com
  placas) e a porta sinc do modelo de cavidade (verificado: a série
  modal converge para ~0.2 nH acima do FDTD, n_modes 30->100). Pela
  sensibilidade df/f = -dL/2L, 0.2/2/2 nH -> ~5%. Na prática esse
  detalhe fica ABAIXO da incerteza de estimar l_mnt do layout
  (+-0.3-0.5 nH), que o usuário calibra por rail.
- razão |Zin| pipeline/hibrido em [0.5, 2] em > 90% da banda 50 MHz-1.4 GHz
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
from pdn import planes, network
from pdn.capacitor import Decap

A, B, D = 100e-3, 80e-3, 0.5e-3
EPS_R, TAN_D = 4.4, 0.02
P_CHIP = (A / 4, B / 4)
P_CAP = (3 * A / 4, B / 2)
CAP = Decap(c=1e-9, esr=50e-3, esl=1e-9, l_mnt=0.0, name='C1')
TOL_PICO = 0.03
TOL_DIP = 0.05     # ver justificativa no docstring


def features(f, zmag):
    from scipy.signal import find_peaks
    zlog = np.log10(zmag)
    pk, _ = find_peaks(zlog, prominence=np.log10(2.0))
    dp, _ = find_peaks(-zlog, prominence=np.log10(2.0))
    return f[pk], f[dp]


def main():
    d = np.loadtxt(HERE / 'zmat_openems.csv', delimiter=',', skiprows=1)
    f = d[:, 0]
    z_fdtd = np.empty((len(f), 2, 2), dtype=complex)
    z_fdtd[:, 0, 0] = d[:, 1] + 1j * d[:, 2]
    z_fdtd[:, 1, 0] = d[:, 3] + 1j * d[:, 4]
    z_fdtd[:, 1, 1] = d[:, 5] + 1j * d[:, 6]
    z_fdtd[:, 0, 1] = d[:, 7] + 1j * d[:, 8]

    z_ana = planes.z_matrix(f, A, B, D, EPS_R, TAN_D, [P_CHIP, P_CAP],
                            n_modes=40)

    zc = CAP.z(f)[:, None]
    zin_hyb = network.reduce_loaded(z_fdtd, [0], [1], zc)[:, 0, 0]
    zin_ana = network.reduce_loaded(z_ana, [0], [1], zc)[:, 0, 0]

    band = (f > 50e6) & (f < 1.4e9)
    fb = f[band]
    pk_h, dp_h = features(fb, np.abs(zin_hyb[band]))
    pk_a, dp_a = features(fb, np.abs(zin_ana[band]))

    rows, all_ok = [], True
    for name, fh, fa, tol in [
        ('dip SRF montada',
         dp_h[0] if len(dp_h) else np.nan,
         dp_a[0] if len(dp_a) else np.nan, TOL_DIP),
        ('pico 1',
         pk_h[0] if len(pk_h) else np.nan,
         pk_a[0] if len(pk_a) else np.nan, TOL_PICO),
        ('pico 2',
         pk_h[1] if len(pk_h) > 1 else np.nan,
         pk_a[1] if len(pk_a) > 1 else np.nan, TOL_PICO),
    ]:
        if np.isnan(fh) or np.isnan(fa):
            rows.append((name, fh, fa, np.nan, False))
            all_ok = False
            continue
        err = abs(fa - fh) / fh
        ok = err < tol
        rows.append((name, fh, fa, err, ok))
        all_ok &= ok

    ratio = np.abs(zin_ana[band]) / np.abs(zin_hyb[band])
    frac_ok = float(np.mean((ratio > 0.5) & (ratio < 2.0)))
    mag_ok = frac_ok > 0.90
    all_ok &= mag_ok

    # reciprocidade da matriz FDTD (sanidade das duas simulações)
    recip = np.median(np.abs(z_fdtd[band, 0, 1] - z_fdtd[band, 1, 0])
                      / np.abs(z_fdtd[band, 1, 0]))

    fig, axs = plt.subplots(2, 1, figsize=(9, 8.5), sharex=True)
    axs[0].semilogy(f / 1e9, np.abs(z_fdtd[:, 1, 0]),
                    label='openEMS (FDTD)', lw=1.8)
    axs[0].semilogy(f / 1e9, np.abs(z_ana[:, 1, 0]), '--',
                    label='Modelo de cavidade', lw=1.5)
    axs[0].set_ylabel('|Z21| [$\\Omega$]')
    axs[0].set_title('Transferência entre portas (planos nus)')
    axs[0].grid(True, which='both', alpha=0.3)
    axs[0].legend()

    axs[1].semilogy(f / 1e9, np.abs(zin_hyb),
                    label='híbrido: Z FDTD + decap por Schur', lw=1.8)
    axs[1].semilogy(f / 1e9, np.abs(zin_ana), '--',
                    label='pipeline: Z analítica + decap por Schur', lw=1.5)
    axs[1].axvline(CAP.srf() / 1e9, color='gray', ls=':', lw=0.8)
    axs[1].set_xlabel('Frequência [GHz]')
    axs[1].set_ylabel('|Zin| no chip [$\\Omega$]')
    axs[1].set_title('Zin com decap 1 nF / 50 m$\\Omega$ / 1 nH')
    axs[1].grid(True, which='both', alpha=0.3)
    axs[1].legend()
    fig.tight_layout()
    fig.savefig(HERE / 'comparison.png', dpi=150)

    lines = [
        '# Caso 4 (v2) — Pipeline PDN vs matriz Z do openEMS\n',
        'Mesmo decap conectado pela mesma redução de Schur sobre a matriz '
        'Z analítica e a matriz Z extraída por FDTD (2 simulações, sonda '
        '1 Mohm). A comparação isola o modelo de planos.\n',
        f'Reciprocidade FDTD |Z12-Z21|/|Z21| (mediana): {recip*100:.2f}%\n',
        '| Feature de Zin | f híbrido [MHz] | f pipeline [MHz] | erro | status |',
        '|---|---:|---:|---:|:---:|',
    ]
    for name, fh, fa, err, ok in rows:
        lines.append(f'| {name} | {fh/1e6:.1f} | {fa/1e6:.1f} '
                     f'| {err*100:.2f}% | {"PASS" if ok else "FAIL"} |')
    lines.append(f'\nMagnitude: razão em [0.5, 2] em {frac_ok*100:.1f}% '
                 f'da banda (critério > 90%): '
                 f'{"PASS" if mag_ok else "FAIL"}\n')
    lines.append('Tolerância do dip = 5% (picos = 3%): a posição do dip '
                 'carrega a indutância local da porta, que difere ~0.2 nH '
                 'entre a porta FDTD discretizada e a porta sinc do modelo '
                 'de cavidade (df/f = -dL/2L ~ 5%). Esse detalhe fica '
                 'abaixo da incerteza pratica de l_mnt (+-0.3-0.5 nH).\n')
    lines.append('Nota de método: a v1 embutia o decap como elemento RLC '
                 'lumped série na FDTD, mas o openEMS (master, LEtype=1) '
                 'ignorou SetInductance — o pico de anti-ressonância caiu '
                 'na posição prevista para L=0. Documentado e contornado '
                 'com a extração da matriz Z.\n')
    verdict = 'APROVADO' if all_ok else 'REPROVADO'
    lines.append(f'**Resultado: {verdict}**\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
