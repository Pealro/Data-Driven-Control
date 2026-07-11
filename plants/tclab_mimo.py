# -*- coding: utf-8 -*-
"""Planta TCLab MIMO: Q1,Q2 (aquecedores) -> T1,T2 (sensores). n=2, m=2.

Requer o firmware firmware/boards/tclab_mimo gravado no Arduino.
"""

from plants.serial_plant import SerialPlant


class TCLabMIMO(SerialPlant):
    def __init__(self, port: str, baud: int = 115200, verbose: bool = True):
        super().__init__(n=2, m=2, port=port, baud=baud, u_min=0.0, u_max=100.0, verbose=verbose)
