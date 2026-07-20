"""Caso 3: gera entradas FastHenry para dois problemas com forma fechada.

a) barra reta 20 x 1 x 1 mm  -> indutância parcial própria (Rosa/Ruehli)
b) par ida-e-volta: duas barras 20 mm separadas 4 mm -> L = 2*(Lp - M)

Frequência baixa (100 Hz): corrente uniforme, regime das fórmulas.
Saída: bar.inp e loop.inp neste diretório.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent

L_MM, W_MM, T_MM = 20.0, 1.0, 1.0
SEP_MM = 4.0
FREQ = 100.0
SIGMA_S_MM = 5.8e4          # cobre: 5.8e7 S/m = 5.8e4 S/mm

COMMON = f"""* {{name}}
.units mm
.default sigma={SIGMA_S_MM} nwinc=9 nhinc=9
"""

bar = COMMON.format(name="barra reta - indutancia parcial propria") + f"""
N1 x=0 y=0 z=0
N2 x={L_MM} y=0 z=0
E1 N1 N2 w={W_MM} h={T_MM}
.external N1 N2
.freq fmin={FREQ} fmax={FREQ} ndec=1
.end
"""

loop = COMMON.format(name="par ida-e-volta - L de laco parcial") + f"""
N1 x=0 y=0 z=0
N2 x={L_MM} y=0 z=0
N3 x={L_MM} y={SEP_MM} z=0
N4 x=0 y={SEP_MM} z=0
E1 N1 N2 w={W_MM} h={T_MM}
E2 N4 N3 w={W_MM} h={T_MM}
* portas: ida pela E1, volta pela E2 (curto ideal na extremidade x=L)
.equiv N2 N3
.external N1 N4
.freq fmin={FREQ} fmax={FREQ} ndec=1
.end
"""

(HERE / 'bar.inp').write_text(bar, encoding='ascii')
(HERE / 'loop.inp').write_text(loop, encoding='ascii')
print('OK: bar.inp, loop.inp')
