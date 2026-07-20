# Caso 9 — PDN do rail MODEM_VCC (Eagle_tracker, placa real)

Geometria/stackup extraídos do Altium via MCP; pipeline dos casos 1-8 (matriz Z FDTD + extensão LF + Schur + target).

Pour 27.27 x 17.17 mm, d = 1.232 mm (core), eps_r 4.2; mismatch Im do lumped LF: 0.75%.

Target: 3.3 V, ripple 3%, burst 2 A -> Zt = 49.5 mohm até 100 MHz.

## A: rail nu
- VIOLA Zt de 0.01 a 1.42e+03 MHz (pior: 20851685.0x)
- VIOLA Zt de 1.55e+03 a 2e+03 MHz (pior: 6.4x)

## B: como esta (so C39)
- VIOLA Zt de 0.01 a 0.137 MHz (pior: 14.6x)
- VIOLA Zt de 2.62 a 1.59e+03 MHz (pior: 1470.3x)
- VIOLA Zt de 1.69e+03 a 2e+03 MHz (pior: 5.7x)

## C: C39 + 100nF no modem
- VIOLA Zt de 0.01 a 0.137 MHz (pior: 14.5x)
- VIOLA Zt de 2.53 a 10.5 MHz (pior: 16.9x)
- VIOLA Zt de 14.5 a 1.61e+03 MHz (pior: 533.1x)
- VIOLA Zt de 1.7e+03 a 2e+03 MHz (pior: 5.1x)


## Interpretação de engenharia
- O cartão mPCIe carrega os próprios decaps de HF: o dever do HOST é a faixa baixa/média. As violações acionáveis são:
  1. **< 137 kHz (14.6x)**: o envelope do burst GSM (217 Hz+) não tem reservatório — falta BULK. Recomendação: 220 uF (polímero/tântalo baixo-ESR) junto ao CN4;
  2. **2.6-30 MHz**: só o C39 não cobre; o 100 nF nos pads 39/41 (cenário C) corta a região de 10-30 MHz e cria o dip local em 12 MHz — recomendado; adicionar um segundo 100 nF nos pads 2/52;
- acima de ~50 MHz a responsabilidade é do cartão (decaps onboard) — as violações de HF do host são esperadas e não acionáveis deste lado;
- o plano contribui pouco aqui: d = 1.23 mm dá C interplano minúscula (~2.6 pF/cm2) — o rail vive dos capacitores, e a indutância de espalhamento do pour (~1-2 nH) define o teto de MF. Consistente com o modelo lumped: mismatch 0.75%.

## Notas de modelagem
- pour aproximado pelo bbox (o MCP não expõe os vértices); os pads mPCIe 2/52 (VBAT secundários) não modelados;
- C39: 22 uF nominal sem derating de DC bias (X5R 16 V a 3.3 V: ~-10-15%);
- l_mnt inclui vias atravessando o core de 1.23 mm — dominante no laço do decap; estimativa +-0.5 nH;
- primeiro modo de cavidade do pour: ~2.7 GHz (fora da banda) -> rail quasi-estático em toda a banda de interesse;
- tan_d 0.02 assumido (stackup não especifica).
