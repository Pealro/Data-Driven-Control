# -*- coding: utf-8 -*-
"""Config gerada automaticamente pelo wizard (Bloco A: "nova planta").
Planta generica com n=4 estado(s), m=4 entrada(s) -- firmware/boards/generic."""

import numpy as np

from config.base import ExperimentConfig
from plants.generic import GenericPlant

PORT = 'COM9'
BAUD = 115200

CONFIG = ExperimentConfig(
    name='Mimo_4x4',
    make_plant=lambda: GenericPlant(n=4, m=4, port=PORT, baud=BAUD),
    T=2000,
    dt=0.005,
    excitation_amplitude=100.0,
    max_expected_state_deviation=6.0,
    rho=0.9,
    ubar=np.array([50.0, 50.0, 50.0, 50.0]),
    settle_duration_s=2.0,
    setpoint=None,
    control_duration_s=0.0,
    seed=0,
)
