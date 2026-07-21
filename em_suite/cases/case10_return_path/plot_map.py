"""Mapa da placa: pours do Int2, trilhas do Bottom e travessias (caso 10)."""

import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
MIL = 0.0254

CORES = {'+3.3VCC': '#f5c343', 'MODEM_VCC': '#e05c5c',
         '+5VCC': '#7cba5c', 'VSYS': '#5c9fe0', 'GND': '#d9d9d9'}


def main():
    fig, ax = plt.subplots(figsize=(7, 13))

    with open(HERE / 'pours_int2.csv') as fh:
        pours = list(csv.DictReader(fh))
    # desenha do maior para o menor (prioridade visual)
    pours.sort(key=lambda p: -(float(p['right']) - float(p['left']))
               * (float(p['top']) - float(p['bottom'])))
    for p in pours:
        left, bottom = float(p['left']) * MIL, float(p['bottom']) * MIL
        w = (float(p['right']) - float(p['left'])) * MIL
        h = (float(p['top']) - float(p['bottom'])) * MIL
        ax.add_patch(Rectangle((left, bottom), w, h,
                               facecolor=CORES.get(p['net'], '#cccccc'),
                               edgecolor='k', lw=0.6, alpha=0.55))
        ax.text(left + w / 2, bottom + h - 2.5, p['net'], ha='center',
                fontsize=8, weight='bold')

    with open(HERE / 'tracks_bottom.csv') as fh:
        for row in csv.DictReader(fh):
            ax.plot([float(row['x1']) * MIL, float(row['x2']) * MIL],
                    [float(row['y1']) * MIL, float(row['y2']) * MIL],
                    color='#3a5a80', lw=0.7, alpha=0.8)

    xs, ys = [], []
    with open(HERE / 'crossings.csv') as fh:
        for row in csv.DictReader(fh):
            if row['power'] == 'False':
                xs.append(float(row['x_mm']))
                ys.append(float(row['y_mm']))
    ax.scatter(xs, ys, marker='x', s=70, color='red', lw=2, zorder=5,
               label=f'{len(xs)} travessias de sinal')

    ax.set_xlim(-2, 52)
    ax.set_ylim(-2, 127)
    ax.set_aspect('equal')
    ax.set_xlabel('x [mm]')
    ax.set_ylabel('y [mm]')
    ax.set_title('Bottom Layer sobre os pours do Int2 (bbox)\n'
                 'X = travessia de fronteira (return path)')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(HERE / 'board_map.png', dpi=130)
    print('OK: board_map.png')


if __name__ == '__main__':
    main()
