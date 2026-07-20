# Caso 5 — Plano PWR com fenda: extrator openEMS + âncoras

Planos 100 x 80 x 0.5 mm; fenda x = 48-52 mm, y = 20-80 mm (ponte de 20 mm em y = 0); portas em (25, 20) e (75, 40).

(C do plano intacto seria 623.3 pF — a extração distingue a área removida.)

| Âncora | Valor | Critério | Status |
|---|---|---|:---:|
| reciprocidade (mediana, 100 MHz+; ver docstring) | 2.55% | < 3% @ 1.2M TS | PASS |
| razão C_fenda/C_intacto vs (A - A_f)/A | 0.955 vs 0.970 (1.51%) | < 3% | PASS |
| C intacto vs eps*A/d (fringing ~+5%) | 660.7 pF vs 623.3 pF (5.99%) | < 8% | PASS |
| L_loop fenda vs intacto | 1.74 nH vs 0.97 nH (1.79x) | > 1.2x | PASS |

**Resultado: APROVADO**
