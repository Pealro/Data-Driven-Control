# -*- coding: utf-8 -*-
"""Planta generica: "nova planta definida pelo usuario" no wizard (runner.py).
Fala com o firmware firmware/boards/generic (N_MAX=4 estados em A0..A3,
M_MAX=4 entradas PWM em pinos 3,5,6,9). O usuario escolhe quantos canais
usar (n<=4, m<=4) na hora -- nao precisa recompilar nem regravar."""

from plants.serial_plant import SerialPlant

N_MAX = 4
M_MAX = 4


class GenericPlant(SerialPlant):
    def __init__(self, n: int, m: int, port: str, baud: int = 115200, verbose: bool = True):
        if not (1 <= n <= N_MAX):
            raise ValueError(
                f"n deve estar entre 1 e {N_MAX} (firmware/boards/generic), recebido {n}"
            )
        if not (1 <= m <= M_MAX):
            raise ValueError(
                f"m deve estar entre 1 e {M_MAX} (firmware/boards/generic), recebido {m}"
            )
        super().__init__(n=n, m=m, port=port, baud=baud, u_min=0.0, u_max=100.0, verbose=verbose)
