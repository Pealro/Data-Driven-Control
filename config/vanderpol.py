# -*- coding: utf-8 -*-
"""Config do oscilador de Van der Pol (planta simulada nao-linear) -- alvo do
controle com modelo de Koopman. Parametros iguais aos do notebook
teste_final_Vanderpool.ipynb / do artigo (mu=1, dt=0.01, 2000 amostras).

Van der Pol so faz sentido com o metodo Koopman (nao-linear, m=1); os campos
rho/ubar/setpoint existem so para caber no ExperimentConfig e sao ignorados por
esse metodo."""

import numpy as np

from config.base import ExperimentConfig
from plants.vanderpol import VanDerPolPlant

CONFIG = ExperimentConfig(
    name="vanderpol",
    make_plant=lambda: VanDerPolPlant(mu=1.0),
    T=2000,
    dt=0.01,
    excitation_amplitude=1.0,   # entrada aleatoria U(-1, 1), como no artigo
    max_expected_state_deviation=5.0,
    rho=0.9,                    # ignorado pelo Koopman (e da LMI de De Persis)
    ubar=np.array([0.0]),       # ignorado (VdP nao assenta em equilibrio)
    settle_duration_s=0.0,
    setpoint=None,
    control_duration_s=20.0,
    seed=0,
)
