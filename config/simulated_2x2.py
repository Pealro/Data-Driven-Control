# -*- coding: utf-8 -*-
"""Config da planta simulada 2x2 (sem hardware) -- util para testar o
algoritmo data-driven offline."""

import numpy as np

from config.base import ExperimentConfig
from plants.simulated import SimulatedLinearPlant

A = np.array([[0.90, 0.10],
              [0.00, 0.85]])
B = np.array([[0.50, 0.00],
              [0.00, 0.30]])
NOISE_STD = 0.01

CONFIG = ExperimentConfig(
    name="simulated_2x2",
    make_plant=lambda: SimulatedLinearPlant(A, B, noise_std=NOISE_STD, seed=1, verbose=False),
    T=60,
    dt=1.0,
    excitation_amplitude=5.0,
    max_expected_state_deviation=50.0,
    rho=0.90,
    ubar=np.zeros(2),
    settle_duration_s=2.0,
    setpoint=np.array([2.0, -1.0]),
    control_duration_s=20.0,
    seed=2,
)
