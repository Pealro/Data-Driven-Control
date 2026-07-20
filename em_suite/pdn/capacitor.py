"""Modelo RLC série de capacitor de desacoplamento.

Z(f) = ESR + jw*(ESL + L_mnt) + 1/(jw*C)

C/ESR/ESL vêm do datasheet (ou do S2P do fabricante — Murata SimSurfing,
TDK etc.); L_mnt é a indutância de montagem (pads + vias até os planos),
tipicamente 0.3-1.5 nH — dominante em cerâmicos pequenos e função do
layout, não do componente. A frequência de ressonância série (SRF
montada) é f_s = 1/(2*pi*sqrt((ESL+L_mnt)*C)).
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Decap:
    """Capacitor de desacoplamento montado."""
    c: float                # F
    esr: float = 10e-3      # ohm
    esl: float = 0.8e-9     # H (do componente)
    l_mnt: float = 0.5e-9   # H (pads + vias do layout)
    name: str = ""

    @property
    def l_total(self):
        return self.esl + self.l_mnt

    def z(self, f):
        """Impedância série [ohm] no array de frequências f [Hz]."""
        w = 2.0 * np.pi * np.asarray(f, dtype=float)
        return (self.esr + 1j * w * self.l_total
                + 1.0 / (1j * w * self.c))

    def srf(self):
        """Frequência de ressonância série montada [Hz]."""
        return 1.0 / (2.0 * np.pi * np.sqrt(self.l_total * self.c))
