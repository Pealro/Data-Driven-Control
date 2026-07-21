"""Caso 7: eigenmodes do Palace (FEM) vs f_mn exatos da cavidade.

Terceiro solver independente da suíte: FEM de elementos de aresta
(Palace/MFEM), contra FDTD (openEMS, caso 1) e a forma fechada. Com
PEC em z = 0/d e PMC nas laterais, a cavidade ideal tem:

    f_mn = c / (2*sqrt(eps_r)) * sqrt((m/a)^2 + (n/b)^2)

Entrada: postpro/eig.csv do Palace (frequências em GHz).
Critério: 4 primeiros modos com erro < 1% (FEM ordem 2, malha 4 mm).
"""

import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from analytic import cavity

A, B, EPS_R = 100e-3, 80e-3, 4.4
N_MODES_CHECK = 4
TOL = 0.01


def read_eigs(path):
    """Lê eig.csv do Palace: colunas m, Re{f} [GHz], Im{f} [GHz], ..."""
    freqs = []
    with open(path) as fh:
        reader = csv.reader(fh)
        header = next(reader)
        for row in reader:
            if not row:
                continue
            freqs.append(float(row[1]) * 1e9)
    return np.array(sorted(freqs)), header


def main():
    f_palace, _ = read_eigs(HERE / 'postpro' / 'eig.csv')

    f_exact = cavity.resonance_freqs(
        A, B, EPS_R,
        modes=((1, 0), (0, 1), (1, 1), (2, 0), (2, 1), (0, 2), (3, 0)))
    modes = list(f_exact.items())[:N_MODES_CHECK]

    rows, all_ok = [], True
    for mode, fe in modes:
        if len(f_palace) == 0:
            rows.append((mode, fe, np.nan, np.nan, False))
            all_ok = False
            continue
        fp = f_palace[np.argmin(np.abs(f_palace - fe))]
        err = abs(fp - fe) / fe
        ok = err < TOL
        rows.append((mode, fe, fp, err, ok))
        all_ok &= ok

    lines = [
        '# Caso 7 — Palace (FEM) vs f_mn exatos\n',
        f'Cavidade {A*1e3:.0f} x {B*1e3:.0f} mm, eps_r = {EPS_R}; '
        'PEC topo/fundo, PMC laterais; FEM ordem 2.\n',
        f'Modos calculados pelo Palace: '
        f'{np.round(f_palace / 1e6, 1).tolist()} MHz\n',
        '| Modo | f exato [MHz] | f Palace [MHz] | erro | status |',
        '|------|---------------:|---------------:|-----:|:------:|',
    ]
    for mode, fe, fp, err, ok in rows:
        lines.append(f'| {mode} | {fe/1e6:.1f} | {fp/1e6:.1f} '
                     f'| {err*100:.3f}% | {"PASS" if ok else "FAIL"} |')
    verdict = 'APROVADO' if all_ok else 'REPROVADO'
    lines.append(f'\nCritério: erro < {TOL*100:.0f}% nos '
                 f'{N_MODES_CHECK} primeiros modos. '
                 f'**Resultado: {verdict}**\n')
    lines.append('Cross-check triplo fechado: forma fechada, FDTD '
                 '(caso 1: 0.20-1.54%) e FEM (este caso) na mesma '
                 'estrutura.\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
