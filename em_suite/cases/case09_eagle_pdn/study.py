"""Caso 9: PDN real do rail MODEM_VCC do Eagle_tracker.

Primeira aplicação do pipeline validado (casos 1-8) a uma placa real,
com geometria/stackup extraídos DIRETO do Altium via MCP (sem Gerber):
pour MODEM_VCC 27.3 x 17.2 mm no Int2 sobre GND sólido no Int1,
d = 1.232 mm (core), eps_r 4.2. Modem = cartão Mini PCIe no CN4
(VBAT nos pads 39/41); alimentação via load switch U10; decap único
C39 = 22 uF X5R 0805.

Cenários no pino do modem:
  A. rail nu (sem decap) — referência
  B. como está: só C39
  C. proposta: C39 + 100 nF 0402 junto aos pads 39/41 do modem

Target: rail 3.3 V, ripple 3%, burst 2 A (classe GSM do cartão mPCIe)
-> Zt = 49.5 mohm plano até 100 MHz, +20 dB/dec acima.

Uso: python study.py  (após a extração zmat_modem_vcc.csv)
Saídas: study.png, report.md
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from pdn import network, target, lowfreq
from pdn.capacitor import Decap

V_RAIL, RIPPLE, DI = 3.3, 0.03, 2.0
F_KNEE = 100e6

# C39 real: 22 uF X5R 16V 0805. ESR/ESL tipicos 0805; l_mnt inclui as
# vias atravessando o core de 1.23 mm ate os planos (dominante aqui).
# Sem derating de DC bias (X5R 16V a 3.3 V: ~-10-15%, nota no report).
C39 = Decap(c=22e-6, esr=4e-3, esl=0.7e-9, l_mnt=1.0e-9, name='C39 22uF')
C_PROP = Decap(c=100e-9, esr=20e-3, esl=0.5e-9, l_mnt=0.8e-9,
               name='100nF 0402 proposto')
BULK = Decap(c=220e-6, esr=25e-3, esl=1.6e-9, l_mnt=1.0e-9,
             name='bulk 220uF polimero proposto')

P_MODEM, P_C39, P_U10, P_PROP, P_PAD2, P_PAD52 = 0, 1, 2, 3, 4, 5


def load_zmat(path, n):
    with open(path) as fh:
        header = fh.readline().strip().split(',')
    d = np.loadtxt(path, delimiter=',', skiprows=1)
    col = {name.strip(): k for k, name in enumerate(header)}
    f = d[:, col['f_Hz']]
    z = np.empty((len(f), n, n), dtype=complex)
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            z[:, i - 1, j - 1] = (d[:, col[f'ReZ{i}{j}']]
                                  + 1j * d[:, col[f'ImZ{i}{j}']])
    return f, z


def main():
    f_hf, z_hf = load_zmat(HERE / 'zmat_modem_vcc.csv', 6)

    # banda confiável do FDTD (>= 80 MHz) + extensão LF até 10 kHz
    hf = f_hf >= 80e6
    f_lf = np.logspace(4, np.log10(60e6), 240)
    z_lf, model_lf, mism = lowfreq.extend_lf(f_hf, z_hf, f_lf,
                                             fit_band=(80e6, 400e6))
    f_all = np.concatenate([f_lf, f_hf[hf]])
    z_all = np.concatenate([z_lf, z_hf[hf]], axis=0)

    zt = target.target_profile(f_all, V_RAIL, RIPPLE, DI, f_knee=F_KNEE)

    cenarios = {
        'A: rail nu': {},
        'B: como esta (so C39)': {P_C39: C39},
        'C: B + 100nF nos pads 39/41': {P_C39: C39, P_PROP: C_PROP},
        'D: C + 100nF pads 2 e 52 + bulk 220uF no U10':
            {P_C39: C39, P_PROP: C_PROP, P_PAD2: C_PROP,
             P_PAD52: C_PROP, P_U10: BULK},
    }

    fig, ax = plt.subplots(figsize=(9.5, 6))
    report = [
        '# Caso 9 — PDN do rail MODEM_VCC (Eagle_tracker, placa real)\n',
        'Geometria/stackup extraídos do Altium via MCP; pipeline dos '
        'casos 1-8 (matriz Z FDTD + extensão LF + Schur + target).\n',
        f'Pour {27.27} x {17.17} mm, d = 1.232 mm (core), eps_r 4.2; '
        f'mismatch Im do lumped LF: {mism*100:.2f}%.\n',
        f'Target: {V_RAIL} V, ripple {RIPPLE*100:.0f}%, burst '
        f'{DI:.0f} A -> Zt = {target.target_z(V_RAIL, RIPPLE, DI)*1e3:.1f}'
        f' mohm até {F_KNEE/1e6:.0f} MHz.\n',
    ]

    for nome, caps in cenarios.items():
        zin = network.z_in(f_all, z_all, P_MODEM, caps)
        ax.loglog(f_all, np.abs(zin), label=nome, lw=1.6)
        viols = target.violations(f_all, np.abs(zin), zt)
        report.append(f'## {nome}')
        if not viols:
            report.append('- atende Zt em toda a banda\n')
        else:
            for f0v, f1v, ratio in viols:
                report.append(
                    f'- VIOLA Zt de {f0v/1e6:.3g} a {f1v/1e6:.3g} MHz '
                    f'(pior: {ratio:.1f}x)')
            report.append('')

    ax.loglog(f_all, zt, 'k--', lw=1.2, label='target impedance')
    ax.axvline(80e6, color='gray', ls=':', lw=0.8)
    ax.text(80e6, ax.get_ylim()[0] * 2, ' LF->FDTD', fontsize=7,
            color='gray')
    ax.set_xlabel('Frequência [Hz]')
    ax.set_ylabel('|Zin| nos pads VBAT do modem [$\\Omega$]')
    ax.set_title('Eagle_tracker MODEM_VCC — Zin no modem por cenário')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(loc='upper left', fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / 'study.png', dpi=150)

    report.append(
        '\n## Interpretação de engenharia\n'
        '- O cartão mPCIe carrega os próprios decaps de HF: o dever do '
        'HOST é a faixa baixa/média. Quantificado pelos cenários:\n'
        '  1. **LF (envelope do burst GSM)**: como está, viola 14.6x '
        'abaixo de 137 kHz; o bulk de 220 uF no U10 (cenário D) derruba '
        'para 1.4x residual abaixo de 14 kHz — RESOLVE na prática. '
        'Recomendação: 220 uF polímero baixo-ESR junto ao U10/CN4;\n'
        '  2. **MF**: os 100 nF nos pads (39/41 e 2/52) cobrem '
        '10-30 MHz; resta um vão de 9.1x em 2.8-7.3 MHz no cenário D — '
        'fecha com um 1 uF 0603 ao lado de qualquer um dos 100 nF;\n'
        '- acima de ~50 MHz a responsabilidade é do cartão (decaps '
        'onboard) — as violações de HF do host são esperadas e não '
        'acionáveis deste lado;\n'
        '- o plano contribui pouco aqui: d = 1.23 mm dá C interplano '
        'minúscula (~3.0 pF/cm2) — o rail vive dos capacitores, e a '
        'indutância de espalhamento do pour (~1-2 nH) define o teto '
        'de MF. Consistente com o modelo lumped: mismatch 0.75%.\n'
        '\n## Notas de modelagem\n'
        '- pour aproximado pelo bbox (o MCP não expõe os vértices); '
        'pads mPCIe 2/52 modelados como portas 5/6;\n'
        '- C39: 22 uF nominal sem derating de DC bias (X5R 16 V a '
        '3.3 V: ~-10-15%);\n'
        '- l_mnt inclui vias atravessando o core de 1.23 mm — dominante '
        'no laço do decap; estimativa +-0.5 nH;\n'
        '- primeiro modo de cavidade do pour: ~2.7 GHz (fora da banda) '
        '-> rail quasi-estático em toda a banda de interesse;\n'
        '- tan_d 0.02 assumido (stackup não especifica).\n')
    (HERE / 'report.md').write_text('\n'.join(report), encoding='utf-8')
    print('\n'.join(report))


if __name__ == '__main__':
    main()
