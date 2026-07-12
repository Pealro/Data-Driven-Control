# -*- coding: utf-8 -*-
"""Calibracao fisica opcional (Bloco A): converte a leitura crua do sensor
(ADC, 0-5V) e o comando cru do atuador (PWM, 0-100%) para a unidade fisica
real da planta, definida pelo usuario no wizard.

So afeta exibicao (CSV, plots ao vivo) e o setpoint que o usuario digita/ve
no Bloco D -- o nucleo data-driven (X0, X1, U0, K) sempre opera em unidade
crua, exatamente como antes. Isso evita ter que re-derivar K num referencial
fisico (o que exigiria transformar o proprio ganho antes de mandar para o
firmware, que so entende valores crus).

Qualquer limite None desativa a conversao correspondente (equivalente a
'd' = desconhecido no wizard): as funcoes viram identidade.
"""

Y_RAW_AT_ZERO = 0.0  # Volts no ADC quando y esta no minimo fisico
Y_RAW_AT_FULL = 5.0  # Volts no ADC (AREF) quando y esta no maximo fisico
U_RAW_AT_ZERO = 0.0  # % de duty PWM quando u esta no minimo fisico
U_RAW_AT_FULL = 100.0  # % de duty PWM quando u esta no maximo fisico


def y_raw_to_physical(y_raw, y_physical_min, y_physical_max):
    if y_physical_min is None or y_physical_max is None:
        return y_raw
    scale = (y_physical_max - y_physical_min) / (Y_RAW_AT_FULL - Y_RAW_AT_ZERO)
    return y_physical_min + (y_raw - Y_RAW_AT_ZERO) * scale


def y_physical_to_raw(y_physical, y_physical_min, y_physical_max):
    if y_physical_min is None or y_physical_max is None:
        return y_physical
    scale = (Y_RAW_AT_FULL - Y_RAW_AT_ZERO) / (y_physical_max - y_physical_min)
    return Y_RAW_AT_ZERO + (y_physical - y_physical_min) * scale


def u_raw_to_physical(u_raw, u_physical_min, u_physical_max):
    if u_physical_min is None or u_physical_max is None:
        return u_raw
    scale = (u_physical_max - u_physical_min) / (U_RAW_AT_FULL - U_RAW_AT_ZERO)
    return u_physical_min + (u_raw - U_RAW_AT_ZERO) * scale


def u_physical_to_raw(u_physical, u_physical_min, u_physical_max):
    if u_physical_min is None or u_physical_max is None:
        return u_physical
    scale = (U_RAW_AT_FULL - U_RAW_AT_ZERO) / (u_physical_max - u_physical_min)
    return U_RAW_AT_ZERO + (u_physical - u_physical_min) * scale
