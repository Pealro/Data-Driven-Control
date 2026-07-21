# Caso 1 — Cavidade plano-a-plano: openEMS vs analítico

Planos 100 x 80 mm, d = 0.5 mm, eps_r = 4.4, tan_d = 0.02, porta em (a/4, b/4).

| Modo | f analítico [MHz] | f openEMS [MHz] | erro | status |
|------|------------------:|----------------:|-----:|:------:|
| (1, 0) | 714.6 | 719.8 | 0.73% | PASS |
| (0, 1) | 893.3 | 891.4 | 0.20% | PASS |
| (1, 1) | 1143.9 | 1161.5 | 1.54% | PASS |

Critério: erro < 2% na frequência de cada ressonância. Gráfico: comparison.png

**Resultado: APROVADO**
