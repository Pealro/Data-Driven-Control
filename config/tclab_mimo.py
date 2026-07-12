# -*- coding: utf-8 -*-
"""Config da planta TCLab MIMO: Q1,Q2 (aquecedores) -> T1,T2 (sensores).

Template -- ajuste os valores apos validar o firmware firmware/boards/tclab_mimo
na placa real (esta configuracao ainda nao foi testada em hardware).
"""

import numpy as np

from config.base import ExperimentConfig
from plants.tclab_mimo import TCLabMIMO

PORT = "COM7"
BAUD = 115200

CONFIG = ExperimentConfig(
    name="tclab_mimo",
    make_plant=lambda: TCLabMIMO(port=PORT, baud=BAUD),
    T=80,
    dt=0.5,
    excitation_amplitude=80.0,
    max_expected_state_deviation=300.0,
    rho=0.95,
    ubar=np.array([0.0, 0.0]),
    settle_duration_s=1.0,
    setpoint=np.array([200.0, 200.0]),
    control_duration_s=300.0,
    seed=0,
)
