# Caso 9 — PDN do rail MODEM_VCC (Eagle_tracker, placa real)

Geometria/stackup extraídos do Altium via MCP; pipeline dos casos 1-8 (matriz Z FDTD + extensão LF + Schur + target).

Pour 27.27 x 17.17 mm, d = 1.232 mm (core), eps_r 4.2; mismatch Im do lumped LF: 0.75%.

Target: 3.3 V, ripple 3%, burst 2 A -> Zt = 49.5 mohm até 100 MHz.

## A: so o caminho via switch (sem caps locais)
- VIOLA Zt de 0.01 a 1.63e+03 MHz (pior: 1555.6x)
- VIOLA Zt de 1.74e+03 a 2e+03 MHz (pior: 4.6x)

## B: como esta (C39 + via switch)
- VIOLA Zt de 0.01 a 0.0991 MHz (pior: 1.9x)
- VIOLA Zt de 3.03 a 1.73e+03 MHz (pior: 1223.1x)
- VIOLA Zt de 1.83e+03 a 2e+03 MHz (pior: 3.9x)

## C: B + 3x100nF nos pads + 1uF
- VIOLA Zt de 0.01 a 0.0955 MHz (pior: 1.9x)
- VIOLA Zt de 2.44 a 2.82 MHz (pior: 1.1x)
- VIOLA Zt de 4.06 a 7.54 MHz (pior: 5.3x)
- VIOLA Zt de 10.8 a 10.8 MHz (pior: 1.1x)
- VIOLA Zt de 15.6 a 2e+03 MHz (pior: 153.5x)

## D: C + bulk 220uF local (opcional)
- VIOLA Zt de 4.06 a 7.54 MHz (pior: 5.6x)
- VIOLA Zt de 10.8 a 10.8 MHz (pior: 1.1x)
- VIOLA Zt de 15.6 a 2e+03 MHz (pior: 50.2x)


## Interpretação de engenharia (v3 — pós-review do usuário)
- CORREÇÃO relevante: a v2 deixava a porta do U10 vazia e concluía "viola 14.6x em LF, falta bulk". Com o caminho real via switch (Ron 50 mohm + C36 220 uF + regulador ativo), a LF fica MARGINAL, não quebrada: o piso através do switch é ~Ron + ESR ~ 60-70 mohm vs target de 49.5 mohm — a 2 A de burst isso é ~120-140 mV de afundamento (~4% de 3.3 V, levemente acima dos 3% assumidos; com burst de 1 A, folga).
- Quem realmente falta é o MEIO da banda: entre ~1 e 50 MHz o caminho via switch está bloqueado (Ron + indutâncias) e o C39 sozinho já saiu de cena — os 3x100 nF nos pads + 1 uF (cenário C) são a correção essencial;
- o bulk 220 uF LOCAL no MODEM_VCC (cenário D) vira OPCIONAL: compra margem em LF ao contornar o Ron (util se o cartão for GSM 2 A; desnecessário para LTE-M ~1 A);
- acima de ~50 MHz a responsabilidade é do cartão (decaps onboard);
- o plano contribui pouco: d = 1.23 mm -> ~3.0 pF/cm2; o rail vive dos capacitores. Mismatch do lumped LF: 0.75%.

## Notas de modelagem
- pour aproximado pelo bbox (o MCP não expõe os vértices); pads mPCIe 2/52 modelados como portas 5/6;
- C39: 22 uF nominal sem derating de DC bias (X5R 16 V a 3.3 V: ~-10-15%);
- l_mnt inclui vias atravessando o core de 1.23 mm — dominante no laço do decap; estimativa +-0.5 nH;
- primeiro modo de cavidade do pour: ~2.7 GHz (fora da banda) -> rail quasi-estático em toda a banda de interesse;
- tan_d 0.02 assumido (stackup não especifica).
