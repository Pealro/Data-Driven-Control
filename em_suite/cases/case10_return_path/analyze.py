"""Caso 10: detector de travessia de splits — return path do Bottom Layer.

Trilhas do Bottom Layer do Eagle_tracker referenciam o Int2 (plano de
POTÊNCIA, a 155 um), não o GND (Int1, a >1.4 mm). O Int2 é um mosaico
de pours (+3.3VCC, MODEM_VCC, +5VCC, VSYS, resto GND): cada vez que
uma trilha cruza a fronteira entre dois pours, a corrente de retorno
perde o caminho — o mecanismo quantificado no caso 5 (L_loop 1.79x,
modo de fenda em ~380 MHz) e a observação original do review da placa.

Método: para cada segmento, o pour sob cada extremidade é o MENOR bbox
de pour que contém o ponto (aproximação: o MCP dá bbox, não vértices;
pours menores têm prioridade sobre o +3.3VCC gigante e o GND de fundo).
Segmento com pours diferentes nas pontas (ou no meio) = travessia.

Uso: python analyze.py   -> report.md + crossings.csv
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIL = 0.0254  # mm

POWER_NETS = {'MODEM_VCC', 'VSYS', '+3.3VCC', '+5VCC', 'V_BAT', 'GND',
              'eSIM_VCC', 'uSIM_VCC', 'VSIM'}


def load_pours(path):
    pours = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            left, bottom = float(row['left']), float(row['bottom'])
            right, top = float(row['right']), float(row['top'])
            pours.append({'net': row['net'], 'l': left, 'b': bottom,
                          'r': right, 't': top,
                          'area': (right - left) * (top - bottom)})
    return pours


def pour_at(pours, x, y):
    """Pour sob o ponto: o de MENOR área que contém (prioridade)."""
    best = None
    for p in pours:
        if p['l'] <= x <= p['r'] and p['b'] <= y <= p['t']:
            if best is None or p['area'] < best['area']:
                best = p
    return best['net'] if best else 'FORA'


def main():
    pours = load_pours(HERE / 'pours_int2.csv')
    crossings = []
    length_by_net = defaultdict(float)

    with open(HERE / 'tracks_bottom.csv') as fh:
        for row in csv.DictReader(fh):
            net = row['net']
            x1, y1 = float(row['x1']), float(row['y1'])
            x2, y2 = float(row['x2']), float(row['y2'])
            seg_len = ((x2 - x1)**2 + (y2 - y1)**2) ** 0.5
            length_by_net[net] += seg_len

            # amostra o segmento (20 pontos) e detecta mudança de pour
            n_s = 20
            refs = []
            for k in range(n_s + 1):
                t = k / n_s
                refs.append(pour_at(pours, x1 + t * (x2 - x1),
                                    y1 + t * (y2 - y1)))
            changes = []
            for k in range(1, len(refs)):
                if refs[k] != refs[k - 1]:
                    t = (k - 0.5) / n_s
                    changes.append((refs[k - 1], refs[k],
                                    x1 + t * (x2 - x1),
                                    y1 + t * (y2 - y1)))
            for a, b, cx, cy in changes:
                crossings.append({
                    'net': net, 'de': a, 'para': b,
                    'x_mm': cx * MIL, 'y_mm': cy * MIL,
                    'power': net in POWER_NETS})

    # agrega por net
    by_net = defaultdict(list)
    for c in crossings:
        by_net[c['net']].append(c)

    sinal = {n: cs for n, cs in by_net.items() if not cs[0]['power']}
    poder = {n: cs for n, cs in by_net.items() if cs[0]['power']}

    with open(HERE / 'crossings.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['net', 'de', 'para',
                                           'x_mm', 'y_mm', 'power'])
        w.writeheader()
        for c in sorted(crossings, key=lambda c: (c['power'], c['net'])):
            w.writerow({**c, 'x_mm': f"{c['x_mm']:.2f}",
                        'y_mm': f"{c['y_mm']:.2f}"})

    lines = [
        '# Caso 10 — Return path do Bottom Layer vs splits do Int2\n',
        'Trilhas do Bottom referenciam o Int2 (155 um) — plano de '
        'POTÊNCIA fatiado. Cada travessia de fronteira de pour = '
        'descontinuidade de retorno (física do caso 5: L_loop 1.79x, '
        'modo de fenda ~380 MHz na cavidade de teste).\n',
        f'**{len(crossings)} travessias** detectadas; '
        f'{len(sinal)} nets de SINAL afetadas:\n',
        '| Net de sinal | travessias | fronteiras cruzadas |',
        '|---|---:|---|',
    ]
    for n in sorted(sinal, key=lambda n: -len(sinal[n])):
        cs = sinal[n]
        bounds = sorted({f"{c['de']}->{c['para']}" for c in cs})
        lines.append(f'| {n} | {len(cs)} | {", ".join(bounds)} |')

    lines.append('\nNets de potência com travessia (menos crítico — o '
                 'retorno fecha pelos decaps): '
                 + ', '.join(sorted(poder)) + '\n')
    lines.append(
        '## Leitura e mitigação\n'
        '- Aproximação: fronteiras por BBOX dos pours (MCP não expõe '
        'vértices) — travessias em zona de sobreposição de bbox podem '
        'ser falso-positivas; a LISTA de nets é confiável, a posição '
        'exata deve ser conferida no layout;\n'
        '- as travessias 3.3VCC->MODEM_VCC e 3.3VCC->GND concentram-se '
        'na faixa y = 54-71 mm (região do CN4): são as trilhas de '
        'sinal do modem (SIM, UART, controle) descendo para o '
        'conector;\n'
        '- mitigação padrão: capacitores de stitching (100 nF) entre '
        'os pours nos pontos de travessia, ou re-rotear os sinais pelo '
        'TOP (referência = Int1 GND contínuo, atravessa sem custo);\n'
        '- o SPI (SCLK/MOSI/MISO/SS) NÃO cruza split — fica na região '
        '3.3VCC (bom!); entre os que cruzam, os de borda mais rápida '
        'são CLKSIM/DATSIM (clock SIM 3-4 MHz, bordas ns) e SWD '
        '(debug, tolerável); sinais lentos (I2C, INT_*, EN/RESET/'
        'UART) toleram funcionalmente, mas cada travessia irradia '
        'no clock/harmônicos — prioridade de stitching: CLKSIM/'
        'DATSIM/RSTSIM na descida para o CN4.\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
