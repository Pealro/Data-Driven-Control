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
| 04 pipeline PDN (openEMS) | Zin com decap: dip SRF + 2 picos | dip < 5%*, picos < 3% | **PASS** 3.9% / 0.34% / 0.69% |
| 05 plano com fenda (openEMS) | recip., C(razão/abs), L_loop, ext. LF | ver report | **PASS** 2.55% / 1.79% / 8.5% / 1.79x / 0.20% |
| ext. LF (lowfreq) | prevê 2 décadas abaixo do ajuste | < 1% vs cavidade | **PASS** (tests/test_lowfreq.py) |

*justificativas das tolerâncias nos docstrings dos compare.py e reports.

Relatórios individuais: `cases/*/report.md`, gráficos em `cases/*/comparison.png`.

### Lição registrada (caso 02)

Com malha W/8 e regra dos terços invertida, o Z0 saiu 46.7 ohm — curva
lisa, plausível e 4% errada. Corrigindo a regra dos terços (linha a res/3
DENTRO do metal, 2*res/3 fora) e refinando para W/12 com 8 células no
substrato: 48.42 ohm (0.54%). Moral: em FDTD, borda de metal mal
resolvida desloca Z0 sistematicamente para baixo sem nenhum sinal visível
na curva — só a âncora analítica denuncia.

## Fase 2 — Pipeline PDN AC (`pdn/`)

Equivalente open source do fluxo PIPro, construído sobre o modelo de
cavidade validado no caso 1:

```
pdn/
  planes.py     # matriz Z multiporta do par de planos (série modal)
  capacitor.py  # Decap: RLC série (C, ESR, ESL + L_mnt), SRF montada
  network.py    # complemento de Schur: decaps como cargas shunt -> Zin
  target.py     # target impedance (Zt = dV/dI) e detecção de violações
```

Uso típico (ver `examples/pdn_rail_bg95.py`):

```python
zmat = planes.z_matrix(f, a, b, d, eps_r, tan_d, ports)
zin  = network.z_in(f, zmat, chip_port=0, decaps_at={1: Decap(c=100e-6), ...})
viols = target.violations(f, abs(zin), target.target_profile(f, 3.8, 0.03, 2.0))
```

Validação da Fase 2:
- `tests/test_pdn.py` (11 testes): identidades exatas (Schur com curto,
  reciprocidade, decap dominante em LF, SRF, anti-ressonância entre caps)
- caso 4: pipeline completo vs openEMS com o capacitor RLC embutido na
  FDTD (`cases/case04_pdn_pipeline/`)

Achado físico registrado nos testes: os planos 100x80x0.5 mm contribuem
~0.95 nH de indutância de espalhamento entre portas — perto da SRF de um
10 uF isso já desvia |Zin| em 2.4%, por isso o teste de limite exato usa
10-50 kHz.

## Fase 3 — Geometria real e modelos de fabricante

- **`pdn/extract_openems.py`** — extrator de matriz Z multiporta por
  FDTD para planos com fendas/recortes (config JSON, N simulações com
  sondas de 1 Mohm, uma por porta). É a saída do retângulo ideal: onde
  o modelo de cavidade deixa de valer, a matriz Z passa a vir do
  openEMS e o resto do pipeline (Decap + Schur + target) é o mesmo.
- **Caso 5** (`cases/case05_split_plane/`) — plano PWR com fenda de
  4 x 60 mm entre as portas (classe do problema de return path do
  Eagle_tracker). Âncoras: reciprocidade, C de baixa frequência
  proporcional à área restante, e aumento da indutância de laço
  porta-a-porta vs plano intacto (matriz do caso 4, mesmo método).
- **`DecapS2P`** (`pdn/capacitor.py`) — capacitor a partir de
  touchstone S2P de fabricante (série ou shunt), com L de montagem
  somada e recusa explícita a extrapolar fora da banda do arquivo.
  Testes de ida-e-volta contra RLC sintético nas duas convenções.
- **`pdn/lowfreq.py`** — extensão de baixa frequência para matrizes Z
  extraídas por FDTD. IMPORTANTE: a limitação de LF é da SIMULAÇÃO
  FDTD (janela finita ~150 ns -> piso útil ~60-80 MHz), não do fluxo:
  abaixo da primeira ressonância o par de planos é quasi-estático
  (Z = R + 1/(jwC) + jwL, exato), e os sinais comuns dessa faixa
  (DC-DC 100 kHz-2 MHz, envelope de burst GSM) são cobertos pelo
  modelo lumped ajustado na banda confiável do FDTD. Validado contra
  o modelo de cavidade (exato em LF): ajuste em 80-250 MHz prevê
  5-30 MHz a < 1% (tests/test_lowfreq.py). O modelo de cavidade
  analítico (pdn/planes) nunca teve limitação de LF — vale de DC a
  GHz; a extensão só é necessária para geometria recortada, onde a
  matriz vem do FDTD.

### Divisão de trabalho por frequência (PDN)

| Faixa | Física | Ferramenta |
|---|---|---|
| DC | IR drop resistivo | solver DC (PDN Analyzer cobre) |
| ~kHz até 1a ressonância | quasi-estático: C + L + R exatos | forma fechada / lumped ajustado (`lowfreq`) |
| acima de ~f_res/2 | ondas: modos de cavidade, fendas | FDTD (`extract_openems`) ou modelo de cavidade |

Notas de precisão do FDTD em LF: Re{Z} pequena sai corrompida pelo
leakage (medido ~6x a 80 MHz) — R de planos em LF deve vir de solver
DC; a métrica de validade quasi-estática do `extend_lf` usa só a parte
imaginária por isso. O termo de perda condutiva delta_s/d do modelo de
cavidade é inválido quando delta_s > espessura do cobre (f < ~5 MHz
p/ 35 um) — superestima a perda; abaixo disso a R real satura na
resistência DC de folha.

## Próximos passos (Fase 4)

- gerber2ems para SI pós-layout a partir dos Gerbers do Altium
- Cross-check openEMS vs Palace (FEM) nos mesmos casos
- Benchmark publicado com medição de terceiros
- Fendas internas (polígono com furo) no extrator
