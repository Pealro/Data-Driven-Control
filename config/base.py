# -*- coding: utf-8 -*-
"""Estrutura comum de configuracao de experimento. Cada planta tem um modulo
config/<planta>.py que expoe uma variavel CONFIG deste tipo."""

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from plants.base import Plant


@dataclass
class ExperimentConfig:
    name: str
    make_plant: Callable[[], Plant]

    T: int                    # janela do experimento (numero de amostras)
    dt: float                 # taxa de amostragem [s]
    amp_entrada: float        # amplitude do desvio de entrada du
    amp_estado: float         # excursao maxima esperada do estado (diagnostico)
    rho: float                # margem de estabilidade (disco de raio rho < 1)

    ubar: np.ndarray          # entrada de equilibrio (m,)
    settle_s: float           # tempo de assentamento em ubar [s]

    setpoint: Optional[np.ndarray]  # setpoint do controle (n,); None => usa ybar medido
    ctrl_s: float              # duracao do controle em malha fechada [s] (0 = infinito)

    seed: Optional[int] = None
