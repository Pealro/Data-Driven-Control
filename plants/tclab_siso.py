# -*- coding: utf-8 -*-
"""Planta TCLab SISO: Q1 (aquecedor 1) -> T1 (sensor 1). n=1, m=1.

Requer o firmware firmware/boards/tclab_siso gravado no Arduino.
"""

from plants.serial_plant import SerialPlant


class TCLabSISO(SerialPlant):
    def __init__(self, port: str, baud: int = 115200, verbose: bool = True):
        super().__init__(n=1, m=1, port=port, baud=baud, u_min=0.0, u_max=100.0, verbose=verbose)
