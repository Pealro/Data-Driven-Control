"""Demo Fase 2: PDN do rail 3.8 V de um modem estilo BG95.

Cenário: placa 60 x 40 mm (classe Eagle_tracker), par de planos
PWR/GND com 0.2 mm de separação. O modem em burst GSM demanda ~2 A;
ripple permitido 3% de 3.8 V -> Zt = 57 mohm, plano até o joelho
(t_rise ~ 10 us do perfil de burst -> f_knee ~ 35 kHz para o envelope;
o conteúdo de chaveamento vai bem além, então mantemos Zt plano até
100 MHz como visão conservadora).

Compara o rail sem decaps, com bulk apenas, e com a rede completa.
Uso: python em_suite/examples/pdn_rail_bg95.py
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'em_suite'))
from pdn import planes, network, target
from pdn.capacitor import Decap

# --- placa e portas -------------------------------------------------------
A, B, D = 60e-3, 40e-3, 0.2e-3
EPS_R, TAN_D = 4.4, 0.02

P_MODEM = (15e-3, 20e-3)          # pinos VBAT do modem
P_BULK = (20e-3, 15e-3)           # bulk perto do modem
P_C1 = (13e-3, 24e-3)             # ceramicos ao redor
P_C2 = (18e-3, 25e-3)
P_C3 = (22e-3, 20e-3)
PORTS = [P_MODEM, P_BULK, P_C1, P_C2, P_C3]

# --- rede de desacoplamento ----------------------------------------------
BULK = Decap(c=100e-6, esr=35e-3, esl=1.4e-9, l_mnt=0.8e-9,
             name='bulk 100 uF')
C100N = Decap(c=100e-9, esr=20e-3, esl=0.6e-9, l_mnt=0.5e-9,
              name='100 nF 0402')
C1U = Decap(c=1e-6, esr=15e-3, esl=0.8e-9, l_mnt=0.5e-9,
            name='1 uF 0603')
C10N = Decap(c=10e-9, esr=30e-3, esl=0.5e-9, l_mnt=0.4e-9,
             name='10 nF 0402')

# --- target ----------------------------------------------------------------
V_RAIL, RIPPLE, DI = 3.8, 0.03, 2.0
F = np.logspace(4, 9, 1200)       # 10 kHz a 1 GHz
ZT = target.target_profile(F, V_RAIL, RIPPLE, DI, f_knee=100e6)


def main():
    zmat = planes.z_matrix(F, A, B, D, EPS_R, TAN_D, PORTS, n_modes=40)

    cenarios = {
        'sem decaps': {},
        'so bulk': {1: BULK},
        'rede completa': {1: BULK, 2: C1U, 3: C100N, 4: C10N},
    }

    fig, ax = plt.subplots(figsize=(9.5, 6))
    report = ['# Demo — PDN do rail 3.8 V (burst GSM 2 A, estilo BG95)\n',
              f'Placa {A*1e3:.0f} x {B*1e3:.0f} mm, planos com '
              f'd = {D*1e3:.1f} mm; Zt = {ZT[0]*1e3:.0f} mohm '
              f'(plano ate 100 MHz, +20 dB/dec acima).\n']

    for nome, caps in cenarios.items():
        zin = network.z_in(F, zmat, 0, caps)
        ax.loglog(F, np.abs(zin), label=nome, lw=1.6)
        viols = target.violations(F, np.abs(zin), ZT)
        report.append(f'## {nome}')
        if not viols:
            report.append('- atende Zt em toda a banda\n')
        else:
            for f0v, f1v, ratio in viols:
                report.append(
                    f'- VIOLA Zt de {f0v/1e6:.3g} MHz a {f1v/1e6:.3g} MHz '
                    f'(pior: {ratio:.1f}x)')
            report.append('')

    ax.loglog(F, ZT, 'k--', lw=1.2, label='target impedance')
    ax.set_xlabel('Frequência [Hz]')
    ax.set_ylabel('|Zin| no modem [$\\Omega$]')
    ax.set_title('PDN rail 3.8 V — evolução com a rede de desacoplamento')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(loc='upper left', fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / 'pdn_rail_bg95.png', dpi=150)
    (HERE / 'pdn_rail_bg95.md').write_text('\n'.join(report),
                                           encoding='utf-8')
    print('\n'.join(report))
    print(f'\nGráfico: {HERE / "pdn_rail_bg95.png"}')


if __name__ == '__main__':
    main()
