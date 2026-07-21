# Caso 6 — gerber2ems vs medição VNA (benchmark de terceiros)

Exemplo stub_short (Antmicro SI Simulation Test Board): Gerbers de produção -> gerber2ems -> openEMS, contra medição VNA distribuída no repositório do gerber2ems.

| Métrica | Valor | Critério | Status |
|---|---|---|:---:|
| MAE de |S11| vs VNA suavizado (0.2-3.5 GHz) | 0.0485 | < 0.05 | PASS |
| correlação de Pearson vs VNA suavizado | 0.9793 | > 0.95 | PASS |
| MAE vs VNA cru (inclui fixture; informativo) | 0.0609 | - | PASS |

**Resultado: APROVADO**
