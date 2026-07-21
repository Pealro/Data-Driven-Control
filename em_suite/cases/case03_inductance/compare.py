"""Caso 3: compara FastHenry com Rosa/Grover (indutância parcial).

Espera os arquivos Zc_bar.mat e Zc_loop.mat gerados pelo FastHenry no WSL
(ver README do caso). Saída: report.md. Critério: erro < 3%.
"""

import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from analytic import inductance

L, W, T = 20e-3, 1e-3, 1e-3
SEP = 4e-3
FREQ = 100.0
TOL = 0.03


def read_fasthenry_l(path):
    """Extrai L [H] do arquivo Zc.mat do FastHenry (matriz 1x1)."""
    txt = Path(path).read_text()
    m = re.search(r'([+-]?[\d.eE+-]+)\s*([+-][\d.eE+-]+)j', txt)
    if not m:
        raise ValueError(f'impedância não encontrada em {path}')
    x = float(m.group(2))
    return x / (2 * np.pi * FREQ)


def main():
    rows, all_ok = [], True

    # a) barra reta: indutância parcial própria
    l_fh = read_fasthenry_l(HERE / 'Zc_bar.mat')
    l_ref = inductance.bar_self(L, W, T)
    err = abs(l_fh - l_ref) / l_ref
    ok = err < TOL
    all_ok &= ok
    rows.append(('barra 20x1x1 mm (Lp própria)', l_ref, l_fh, err, ok))

    # b) par ida-e-volta: L = 2*(Lp - M), M na distância GMD ~ centro-a-centro
    l_fh = read_fasthenry_l(HERE / 'Zc_loop.mat')
    l_ref = 2.0 * (inductance.bar_self(L, W, T)
                   - inductance.wires_mutual(L, SEP))
    err = abs(l_fh - l_ref) / l_ref
    ok = err < TOL
    all_ok &= ok
    rows.append(('par ida-e-volta, s = 4 mm', l_ref, l_fh, err, ok))

    lines = [
        '# Caso 3 — Indutância parcial: FastHenry vs Rosa/Grover\n',
        '| Estrutura | L analítico [nH] | L FastHenry [nH] | erro | status |',
        '|---|---:|---:|---:|:---:|',
    ]
    for name, lr, lf, err, ok in rows:
        lines.append(f'| {name} | {lr*1e9:.3f} | {lf*1e9:.3f} '
                     f'| {err*100:.2f}% | {"PASS" if ok else "FAIL"} |')
    verdict = 'APROVADO' if all_ok else 'REPROVADO'
    lines.append(f'\nCritério: erro < {TOL*100:.0f}%. '
                 f'**Resultado: {verdict}**\n')
    (HERE / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
