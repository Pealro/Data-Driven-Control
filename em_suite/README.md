# em_suite — Suíte de validação para fluxo EM open source (PDN/SI)

Fase 1 do projeto de reproduzir as capacidades PIPro/SIPro com ferramentas
abertas (openEMS, FastHenry, gerber2ems). Esta suíte ancora o fluxo em
**casos canônicos com resposta exata conhecida** — a âncora de validação
que substitui a medição de bancada (VNA/TDR indisponíveis).

## Estratégia de validação (3 âncoras, sem hardware)

1. **Forma fechada exata**: cavidade plano-a-plano (f_mn e modelo de
   cavidade completo), microstrip (Hammerstad-Jensen), indutância parcial
   (Rosa/Grover). O solver tem que reproduzir esses valores.
2. **Concordância entre solvers independentes**: openEMS (FDTD) vs Palace
   (FEM) na mesma estrutura — métodos numéricos diferentes, mesmo
   resultado (fase posterior).
3. **Benchmark publicado com medição de terceiros** (fase posterior).

## Estrutura

```
em_suite/
  analytic/          # referências analíticas (testadas: 11 testes)
    cavity.py        # f_mn + Z(f) do par de planos (modelo de cavidade)
    microstrip.py    # Z0/eps_eff Hammerstad-Jensen 1980
    inductance.py    # indutância parcial Rosa/Grover/Ruehli
  tests/
    test_analytic.py # âncoras: limites exatos + valores publicados
  cases/
    case01_cavity/   # openEMS vs modelo de cavidade (PDN)
      run_openems.py #   roda no WSL:  source ~/venv-em/bin/activate
      compare.py     #   compara, gera comparison.png + report.md
```

## Ambiente

- **Windows**: Python 3.11 (numpy/scipy/matplotlib/scikit-rf/pytest) —
  módulo analítico, testes e pós-processamento.
- **WSL Ubuntu 24.04**: openEMS compilado do fonte em `~/opt/openEMS`
  (branch master, `--python --disable-GUI`), venv em `~/venv-em`.
  Build: `~/openEMS-Project/update_openEMS.sh` (log em `~/build_openems.log`).

## Rodar

```powershell
# testes das referências analíticas (Windows)
python -m pytest em_suite/tests -v

# caso 1 (solver no WSL, comparação no Windows)
wsl -d Ubuntu-24.04 -- bash -lc "source ~/venv-em/bin/activate && cd /mnt/c/<repo>/em_suite/cases/case01_cavity && python run_openems.py"
python em_suite/cases/case01_cavity/compare.py
```

## Resultados (2026-07-20) — Fase 1 completa

| Caso | Grandeza | Critério | Resultado |
|------|----------|----------|-----------|
| 01 cavidade (openEMS) | f das 3 primeiras ressonâncias | < 2% vs f_mn exato | **PASS** 0.20-1.54%; curvas Z(f) sobrepostas na banda toda |
| 02 microstrip (openEMS) | Z0 quase-estático | < 3% vs H-J | **PASS** 0.54% (48.42 vs 48.69 ohm) |
| 03 indutância (FastHenry) | L parcial barra + par ida-e-volta | < 3% vs Rosa/Grover | **PASS** 0.08% / 0.03% |

Relatórios individuais: `cases/*/report.md`, gráficos em `cases/*/comparison.png`.

### Lição registrada (caso 02)

Com malha W/8 e regra dos terços invertida, o Z0 saiu 46.7 ohm — curva
lisa, plausível e 4% errada. Corrigindo a regra dos terços (linha a res/3
DENTRO do metal, 2*res/3 fora) e refinando para W/12 com 8 células no
substrato: 48.42 ohm (0.54%). Moral: em FDTD, borda de metal mal
resolvida desloca Z0 sistematicamente para baixo sem nenhum sinal visível
na curva — só a âncora analítica denuncia.

## Próximos passos (Fase 2)

- Pipeline PDN AC parametrizado (planos + capacitores via S-params
  de fabricante + varredura Z(f) no ngspice/Xyce + scikit-rf)
- gerber2ems para SI pós-layout a partir dos Gerbers do Altium
- Cross-check openEMS vs Palace (FEM) nos mesmos casos
- Benchmark publicado com medição de terceiros
