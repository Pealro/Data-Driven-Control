# Caso 10 — Return path do Bottom Layer vs splits do Int2

Trilhas do Bottom referenciam o Int2 (155 um) — plano de POTÊNCIA fatiado. Cada travessia de fronteira de pour = descontinuidade de retorno (física do caso 5: L_loop 1.79x, modo de fenda ~380 MHz na cavidade de teste).

**32 travessias** detectadas; 17 nets de SINAL afetadas:

| Net de sinal | travessias | fronteiras cruzadas |
|---|---:|---|
| I2C_SCL | 4 | +3.3VCC->GND, +3.3VCC->MODEM_VCC, GND->+3.3VCC |
| SWD_IO | 3 | +3.3VCC->GND, +3.3VCC->MODEM_VCC, MODEM_VCC->+3.3VCC |
| RESET | 3 | +3.3VCC->MODEM_VCC, GND->+3.3VCC, MODEM_VCC->+3.3VCC |
| SWD_CLK | 3 | +3.3VCC->GND, +3.3VCC->MODEM_VCC, MODEM_VCC->+3.3VCC |
| BMS_RST | 3 | GND->+3.3VCC, GND->VSYS, VSYS->+3.3VCC |
| I2C_SDA | 2 | +3.3VCC->MODEM_VCC |
| TEMP_EXT3 | 2 | +3.3VCC->MODEM_VCC, MODEM_VCC->+3.3VCC |
| DATSIM | 1 | +3.3VCC->MODEM_VCC |
| UART1_RXD | 1 | +3.3VCC->GND |
| LTE_RX | 1 | +3.3VCC->MODEM_VCC |
| WAKEUP_LTE | 1 | +3.3VCC->MODEM_VCC |
| LTE_TX | 1 | +3.3VCC->MODEM_VCC |
| TEMP_EXT2 | 1 | +3.3VCC->MODEM_VCC |
| UART1_TXD | 1 | +3.3VCC->GND |
| RSTSIM | 1 | +3.3VCC->MODEM_VCC |
| CLKSIM | 1 | +3.3VCC->MODEM_VCC |
| INT_ACCEL1 | 1 | +3.3VCC->MODEM_VCC |

Nets de potência com travessia (menos crítico — o retorno fecha pelos decaps): MODEM_VCC, VSIM

## Leitura e mitigação
- Aproximação: fronteiras por BBOX dos pours (MCP não expõe vértices) — travessias em zona de sobreposição de bbox podem ser falso-positivas; a LISTA de nets é confiável, a posição exata deve ser conferida no layout;
- as travessias 3.3VCC->MODEM_VCC e 3.3VCC->GND concentram-se na faixa y = 54-71 mm (região do CN4): são as trilhas de sinal do modem (SIM, UART, controle) descendo para o conector;
- mitigação padrão: capacitores de stitching (100 nF) entre os pours nos pontos de travessia, ou re-rotear os sinais pelo TOP (referência = Int1 GND contínuo, atravessa sem custo);
- o SPI (SCLK/MOSI/MISO/SS) NÃO cruza split — fica na região 3.3VCC (bom!); entre os que cruzam, os de borda mais rápida são CLKSIM/DATSIM (clock SIM 3-4 MHz, bordas ns) e SWD (debug, tolerável); sinais lentos (I2C, INT_*, EN/RESET/UART) toleram funcionalmente, mas cada travessia irradia no clock/harmônicos — prioridade de stitching: CLKSIM/DATSIM/RSTSIM na descida para o CN4.
