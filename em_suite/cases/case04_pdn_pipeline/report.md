# Caso 4 (v2) — Pipeline PDN vs matriz Z do openEMS

Mesmo decap conectado pela mesma redução de Schur sobre a matriz Z analítica e a matriz Z extraída por FDTD (2 simulações, sonda 1 Mohm). A comparação isola o modelo de planos.

Reciprocidade FDTD |Z12-Z21|/|Z21| (mediana): 0.32%

| Feature de Zin | f híbrido [MHz] | f pipeline [MHz] | erro | status |
|---|---:|---:|---:|:---:|
| dip SRF montada | 113.8 | 109.4 | 3.88% | PASS |
| pico 1 | 217.4 | 216.7 | 0.34% | PASS |
| pico 2 | 741.5 | 736.3 | 0.69% | PASS |

Magnitude: razão em [0.5, 2] em 92.2% da banda (critério > 90%): PASS

Tolerância do dip = 5% (picos = 3%): a posição do dip carrega a indutância local da porta, que difere ~0.2 nH entre a porta FDTD discretizada e a porta sinc do modelo de cavidade (df/f = -dL/2L ~ 5%). Esse detalhe fica abaixo da incerteza pratica de l_mnt (+-0.3-0.5 nH).

Nota de método: a v1 embutia o decap como elemento RLC lumped série na FDTD, mas o openEMS (master, LEtype=1) ignorou SetInductance — o pico de anti-ressonância caiu na posição prevista para L=0. Documentado e contornado com a extração da matriz Z.

**Resultado: APROVADO**
