# Caso 9 — PDN do rail MODEM_VCC (Eagle_tracker, placa real)

Geometria/stackup extraídos do Altium via MCP; pipeline dos casos 1-8 (matriz Z FDTD + extensão LF + Schur + target).

Pour 27.27 x 17.17 mm, d = 1.232 mm (core), eps_r 4.2; mismatch Im do lumped LF: 0.75%.

Target: 3.3 V, ripple 3%, burst 2 A -> Zt = 49.5 mohm até 100 MHz.

## A: rail nu
- VIOLA Zt de 0.01 a 1.44e+03 MHz (pior: 21032899.5x)
- VIOLA Zt de 1.57e+03 a 2e+03 MHz (pior: 6.2x)

## B: como esta (so C39)
- VIOLA Zt de 0.01 a 0.137 MHz (pior: 14.6x)
- VIOLA Zt de 2.62 a 1.6e+03 MHz (pior: 1539.8x)
- VIOLA Zt de 1.71e+03 a 2e+03 MHz (pior: 5.4x)

## C: B + 100nF nos pads 39/41
- VIOLA Zt de 0.01 a 0.137 MHz (pior: 14.5x)
- VIOLA Zt de 2.53 a 10.5 MHz (pior: 18.2x)
- VIOLA Zt de 14.5 a 1.62e+03 MHz (pior: 559.1x)
- VIOLA Zt de 1.71e+03 a 2e+03 MHz (pior: 4.9x)

## D: C + 100nF pads 2 e 52 + bulk 220uF no U10
- VIOLA Zt de 0.01 a 0.0139 MHz (pior: 1.4x)
- VIOLA Zt de 2.82 a 7.27 MHz (pior: 9.1x)
- VIOLA Zt de 10.8 a 10.8 MHz (pior: 1.1x)
- VIOLA Zt de 15.6 a 2e+03 MHz (pior: 372.6x)


## Interpretação de engenharia
- O cartão mPCIe carrega os próprios decaps de HF: o dever do HOST é a faixa baixa/média. Quantificado pelos cenários:
  1. **LF (envelope do burst GSM)**: como está, viola 14.6x abaixo de 137 kHz; o bulk de 220 uF no U10 (cenário D) derruba para 1.4x residual abaixo de 14 kHz — RESOLVE na prática. Recomendação: 220 uF polímero baixo-ESR junto ao U10/CN4;
  2. **MF**: os 100 nF nos pads (39/41 e 2/52) cobrem 10-30 MHz; resta um vão de 9.1x em 2.8-7.3 MHz no cenário D — fecha com um 1 uF 0603 ao lado de qualquer um dos 100 nF;
- acima de ~50 MHz a responsabilidade é do cartão (decaps onboard) — as violações de HF do host são esperadas e não acionáveis deste lado;
- o plano contribui pouco aqui: d = 1.23 mm dá C interplano minúscula (~3.0 pF/cm2) — o rail vive dos capacitores, e a indutância de espalhamento do pour (~1-2 nH) define o teto de MF. Consistente com o modelo lumped: mismatch 0.75%.

## Notas de modelagem
- pour aproximado pelo bbox (o MCP não expõe os vértices); pads mPCIe 2/52 modelados como portas 5/6;
- C39: 22 uF nominal sem derating de DC bias (X5R 16 V a 3.3 V: ~-10-15%);
- l_mnt inclui vias atravessando o core de 1.23 mm — dominante no laço do decap; estimativa +-0.5 nH;
- primeiro modo de cavidade do pour: ~2.7 GHz (fora da banda) -> rail quasi-estático em toda a banda de interesse;
- tan_d 0.02 assumido (stackup não especifica).
