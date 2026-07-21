# Caso 7 — Palace (FEM) vs f_mn exatos

Cavidade 100 x 80 mm, eps_r = 4.4; PEC topo/fundo, PMC laterais; FEM ordem 2.

Modos calculados pelo Palace: [714.6, 893.3, 1143.9, 1429.2, 1685.4, 1786.5, 1924.1, 2143.8] MHz

| Modo | f exato [MHz] | f Palace [MHz] | erro | status |
|------|---------------:|---------------:|-----:|:------:|
| (1, 0) | 714.6 | 714.6 | 0.000% | PASS |
| (0, 1) | 893.3 | 893.3 | 0.000% | PASS |
| (1, 1) | 1143.9 | 1143.9 | 0.000% | PASS |
| (2, 0) | 1429.2 | 1429.2 | 0.000% | PASS |

Critério: erro < 1% nos 4 primeiros modos. **Resultado: APROVADO**

Cross-check triplo fechado: forma fechada, FDTD (caso 1: 0.20-1.54%) e FEM (este caso) na mesma estrutura.
