"""Modelo RLC série de capacitor de desacoplamento.

Z(f) = ESR + jw*(ESL + L_mnt) + 1/(jw*C)

C/ESR/ESL vêm do datasheet (ou do S2P do fabricante — Murata SimSurfing,
TDK etc.); L_mnt é a indutância de montagem (pads + vias até os planos),
tipicamente 0.3-1.5 nH — dominante em cerâmicos pequenos e função do
layout, não do componente. A frequência de ressonância série (SRF
montada) é f_s = 1/(2*pi*sqrt((ESL+L_mnt)*C)).
"""

from dataclasses import dataclass, field

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


@dataclass
class DecapS2P:
    """Capacitor a partir de touchstone S2P de fabricante (Murata
    SimSurfing, TDK SEAT etc.), mais indutância de montagem do layout.

    mode: como o fabricante mediu o DUT no fixture de 2 portas —
    'series' (em série entre as portas, o mais comum):
        Z_dut = 2*Z0*(1 - S21)/S21
    'shunt' (em derivação para o terra):
        Z_dut = (Z0/2)*S21/(1 - S21)

    Fora da banda do arquivo, extrapola com o RLC equivalente ajustado
    nas bordas? Não: levanta erro — extrapolar S-params é o erro
    clássico. Garanta que o arquivo cubra a banda da análise.
    """
    path: str
    l_mnt: float = 0.5e-9
    mode: str = 'series'
    name: str = ''
    _f: np.ndarray = field(init=False, repr=False, default=None)
    _z: np.ndarray = field(init=False, repr=False, default=None)

    def __post_init__(self):
        import skrf
        nw = skrf.Network(str(self.path))
        z0 = float(np.real(nw.z0[0, 0]))
        s21 = nw.s[:, 1, 0]
        if self.mode == 'series':
            z_dut = 2.0 * z0 * (1.0 - s21) / s21
        elif self.mode == 'shunt':
            z_dut = (z0 / 2.0) * s21 / (1.0 - s21)
        else:
            raise ValueError("mode deve ser 'series' ou 'shunt'")
        self._f = nw.f
        self._z = z_dut
        if not self.name:
            self.name = str(self.path)

    def z(self, f):
        """Z [ohm] interpolada do S2P + jw*L_mnt. Erro fora da banda."""
        f = np.asarray(f, dtype=float)
        if f.min() < self._f.min() * 0.999 or f.max() > self._f.max() * 1.001:
            raise ValueError(
                f'banda pedida [{f.min():.3g}, {f.max():.3g}] Hz fora do '
                f'S2P [{self._f.min():.3g}, {self._f.max():.3g}] Hz — '
                'não extrapolo S-params')
        zr = np.interp(f, self._f, self._z.real)
        zi = np.interp(f, self._f, self._z.imag)
        return zr + 1j * (zi + 2.0 * np.pi * f * self.l_mnt)
