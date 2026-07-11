# -*- coding: utf-8 -*-
"""Config da planta TCLab SISO: Q1 (aquecedor 1) -> T1 (sensor 1).

Mesmos valores usados em pc_datadriven_tclab.py (legado).
"""

import numpy as np

from config.base import ExperimentConfig
from plants.tclab_siso import TCLabSISO

PORT = "COM7"    # porta serial do Arduino (ex.: "COM3", "/dev/ttyACM0")
BAUD = 115200

CONFIG = ExperimentConfig(
    name="tclab_siso",
    make_plant=lambda: TCLabSISO(port=PORT, baud=BAUD),
    T=100,
    dt=0.5,
    amp_entrada=100.0,
    amp_estado=300.0,
    rho=0.95,
    ubar=np.array([0.0]),
    settle_s=1.0,
    setpoint=np.array([200.0]),
    ctrl_s=300.0,
    seed=0,
)
