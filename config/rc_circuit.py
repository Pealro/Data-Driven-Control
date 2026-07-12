# -*- coding: utf-8 -*-
"""Config da planta RC: pino 3 = sinal PWM (entrada), A0 = tensao no
capacitor (estado). dt/T conservadores -- NAO usamos a constante de tempo
real do circuito de proposito (abordagem data-driven: a planta e tratada
como caixa-preta, mesmo quando o tau e conhecido)."""

import numpy as np

from config.base import ExperimentConfig
from plants.rc_circuit import RCCircuit

PORT = "COM7"
BAUD = 115200

CONFIG = ExperimentConfig(
    name="rc_circuit",
    make_plant=lambda: RCCircuit(port=PORT, baud=BAUD),
    T=2000,  # janela grande -- viavel agora que o firmware gera delta_u(k) sob demanda
             # (sem buffer O(T) em RAM, ver firmware/lib/DataDrivenProtocol)
    dt=0.005,  # confirmado com R/C ajustados (tau ~30-100ms, regra dt~tau/10)
    excitation_amplitude=100.0,  # delta_u em torno de ubar=50% -> u entre 10% e 90%
    max_expected_state_deviation=6.0,  # V (folga acima da faixa fisica 0..5V)
    rho=0.90,
    ubar=np.array([50.0]),  # duty de equilibrio [%]
    settle_duration_s=2.0,
    setpoint=np.array([5]),  # V
    control_duration_s=2.0,
    seed=0,
)
