# -*- coding: utf-8 -*-
"""Planta RC (circuito RC simples): pino 3 = sinal/alimentacao PWM (0..100%
duty), A0 = leitura de tensao no capacitor (0..5V, AREF padrao). n=1, m=1.

Requer o firmware firmware/boards/rc_circuit gravado no Arduino.
"""

from plants.serial_plant import SerialPlant


class RCCircuit(SerialPlant):
    def __init__(self, port: str, baud: int = 115200, verbose: bool = True):
        super().__init__(n=1, m=1, port=port, baud=baud, u_min=0.0, u_max=100.0, verbose=verbose)
