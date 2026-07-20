"""Caso 5: plano PWR com fenda — âncoras físicas da matriz Z extraída.

O modelo de cavidade retangular não cobre planos recortados; aqui o
extrator openEMS (pdn/extract_openems.py) é validado no regime onde
formas fechadas ainda existem, e o efeito da fenda é quantificado
contra o plano intacto (matriz do caso 4, mesmas portas e método).

Âncoras (bandas e formas aprendidas na primeira rodada — ver report):
1. Reciprocidade: mediana |Z12 - Z21|/|Z21| em 100 MHz+ < 3% no
   orçamento de 1.2M timesteps. Mede a qualidade da DFT, não a física:
   o ring-down truncado viola reciprocidade numericamente. Medido:
   3.71% com 400k TS -> 2.55% com 1.2M TS (janela 3x) — a convergência
   com a janela confirma a causa. A estrutura fenda+ilhas ressoa com Q
   alto (slotline + tanque ponte-ilha); para < 1% estimam-se >3M TS.
   Estruturas intactas dão 0.32% já com 400k (caso 4). Para uso no
   pipeline, simetrizar (Z+Z^T)/2 é prática padrão.
2. C de baixa frequência por AJUSTE DE 2 PARÂMETROS em 80-250 MHz:
   Im{Z11} = -1/(wC) + wL (unidades normalizadas, Grad/s — sem isso o
   lstsq descarta a coluna capacitiva por escala). Abaixo de ~60 MHz o
   FDTD é não confiável (janela finita); ler C puro a 30-60 MHz também
   erra +25% por ignorar o termo wL. Critérios:
   - razão C_fenda/C_intacto = (A - A_fenda)/A dentro de 3% (o
     diferencial cancela o fringing das bordas externas);
   - C_intacto vs eps*A/d dentro de 8% (a fórmula de placas ignora o
     fringing, que o FDTD captura: ~+5% nesta geometria);
3. Física da fenda: L_loop = Im{Z11 - Z12 - Z21 + Z22}/w (80-200 MHz)
   deve AUMENTAR vs plano intacto (> 1.2x) — o mecanismo que pune
   return path cruzando split (caso Eagle_tracker).
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

A, B, D = 100e-3, 80e-3, 0.5e-3
EPS_R = 4.4
SLOT = (48e-3, 20e-3, 52e-3, 80e-3)
EPS0 = 8.8541878128e-12


def load_zmat(path):
    """Carrega CSV de matriz Z 2x2 usando os nomes do cabeçalho."""
    with open(path) as fh:
        header = fh.readline().strip().lstrip('#').split(',')
    d = np.loadtxt(path, delimiter=',', skiprows=1)
    col = {name.strip(): k for k, name in enumerate(header)}
    f = d[:, col['f_Hz']]
    z = np.empty((len(f), 2, 2), dtype=complex)
    for i in (1, 2):
        for j in (1, 2):
            z[:, i - 1, j - 1] = (d[:, col[f'ReZ{i}{j}']]
                                  + 1j * d[:, col[f'ImZ{i}{j}']])
    return f, z


def fit_c_l(f, z11, f0=80e6, f1=250e6):
    """Ajusta Im{Z11} = -1/(wC) + wL em unidades normalizadas (Grad/s).

    Sem a normalização as colunas diferem por ~18 ordens de grandeza e
    o lstsq descarta a coluna capacitiva (rcond) — o ajuste 'converge'
    para C infinito e L negativo.
    """
    m = (f >= f0) & (f <= f1)
    wg = 2 * np.pi * f[m] / 1e9
    a_mat = np.column_stack([-1.0 / wg, wg])
    coef, *_ = np.linalg.lstsq(a_mat, z11[m].imag, rcond=None)
    return 1e-9 / coef[0], coef[1] * 1e-9


def main():
    f, zs = load_zmat(HERE / 'zmat_slot.csv')
    fr, zr = load_zmat(HERE.parent / 'case04_pdn_pipeline'
                       / 'zmat_openems.csv')
    assert np.allclose(f, fr), 'grades de frequência diferentes'

    rows, all_ok = [], True

    # 1. reciprocidade (banda confiável da DFT)
    band = (f > 100e6) & (f < 1.4e9)
    recip = np.median(np.abs(zs[band, 0, 1] - zs[band, 1, 0])
                      / np.abs(zs[band, 1, 0]))
    ok = recip < 0.03
    rows.append(('reciprocidade (mediana, 100 MHz+; ver docstring)',
                 f'{recip*100:.2f}%', '< 3% @ 1.2M TS', ok))
    all_ok &= ok

    # 2. capacitância por ajuste C+L
    c_slot, _ = fit_c_l(f, zs[:, 0, 0])
    c_rect, _ = fit_c_l(f, zr[:, 0, 0])
    a_slot = (SLOT[2] - SLOT[0]) * (SLOT[3] - SLOT[1])
    c_eff = EPS0 * EPS_R * (A * B - a_slot) / D
    c_full = EPS0 * EPS_R * A * B / D

    ratio_meas = c_slot / c_rect
    ratio_theo = (A * B - a_slot) / (A * B)
    err_r = abs(ratio_meas - ratio_theo) / ratio_theo
    ok = err_r < 0.03
    rows.append(('razão C_fenda/C_intacto vs (A - A_f)/A',
                 f'{ratio_meas:.3f} vs {ratio_theo:.3f} '
                 f'({err_r*100:.2f}%)', '< 3%', ok))
    all_ok &= ok

    err_c = abs(c_rect - c_full) / c_full
    ok = err_c < 0.08
    rows.append(('C intacto vs eps*A/d (fringing ~+5%)',
                 f'{c_rect*1e12:.1f} pF vs {c_full*1e12:.1f} pF '
                 f'({err_c*100:.2f}%)', '< 8%', ok))
    all_ok &= ok

    # 3. indutância de laço porta-a-porta: fenda vs intacto
    mid = (f >= 80e6) & (f <= 200e6)
    w = 2 * np.pi * f[mid]

    def l_loop(z):
        zl = z[mid, 0, 0] - z[mid, 0, 1] - z[mid, 1, 0] + z[mid, 1, 1]
        return float(np.mean(zl.imag / w))

    l_slot, l_rect = l_loop(zs), l_loop(zr)
    ratio = l_slot / l_rect
    ok = ratio > 1.2
    rows.append(('L_loop fenda vs intacto',
                 f'{l_slot*1e9:.2f} nH vs {l_rect*1e9:.2f} nH '
                 f'({ratio:.2f}x)', '> 1.2x', ok))
    all_ok &= ok

    # --- gráfico ----------------------------------------------------------
    fig, axs = plt.subplots(2, 1, figsize=(9, 8.5), sharex=True)
    axs[0].semilogy(f / 1e9, np.abs(zr[:, 0, 0]), label='intacto', lw=1.5)
    axs[0].semilogy(f / 1e9, np.abs(zs[:, 0, 0]), label='com fenda', lw=1.5)
    axs[0].set_ylabel('|Z11| [$\\Omega$]')
    axs[0].set_title('Efeito da fenda no plano PWR (fenda 4 x 60 mm '
                     'entre as portas)')
    axs[0].grid(True, which='both', alpha=0.3)
    axs[0].legend()
    axs[1].semilogy(f / 1e9, np.abs(zr[:, 1, 0]), label='intacto', lw=1.5)
    axs[1].semilogy(f / 1e9, np.abs(zs[:, 1, 0]), label='com fenda', lw=1.5)
    axs[1].set_xlabel('Frequência [GHz]')
    axs[1].set_ylabel('|Z21| [$\\Omega$]')
    axs[1].grid(True, which='both', alpha=0.3)
    axs[1].legend()
    fig.tight_layout()
    fig.savefig(HERE / 'comparison.png', dpi=150)

    lines = [
        '# Caso 5 — Plano PWR com fenda: extrator openEMS + âncoras\n',
        f'Planos {A*1e3:.0f} x {B*1e3:.0f} x {D*1e3:.1f} mm; fenda '
        f'x = {SLOT[0]*1e3:.0f}-{SLOT[2]*1e3:.0f} mm, '
        f'y = {SLOT[1]*1e3:.0f}-{SLOT[3]*1e3:.0f} mm (ponte de '
        f'{SLOT[1]*1e3:.0f} mm em y = 0); portas em (25, 20) e (75, 40).\n',
        f'(C do plano intacto seria {c_full*1e12:.1f} pF — a extração '
        f'distingue a área removida.)\n',
        '| Âncora | Valor | Critério | Status |',
        '|---|---|---|:---:|',
    ]
    for name, val, crit, ok in rows:
        lines.append(f'| {name} | {val} | {crit} '
                     f'| {"PASS" if ok else "FAIL"} |')
    verdict = 'APROVADO' if all_ok else 'REPROVADO'
    lines.append(f'\n**Resultado: {verdict}**\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
