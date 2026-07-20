"""Testes do módulo analítico contra valores exatos/publicados.

Cada teste ancora uma fórmula num resultado independente: limite físico
exato, valor publicado na literatura, ou forma fechada alternativa.
Rodar: python -m pytest em_suite/tests -v   (da raiz do repositório)
"""

import numpy as np
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytic import cavity, microstrip, inductance


# ---------------------------------------------------------------- cavidade

A, B, D = 100e-3, 80e-3, 0.5e-3   # cavidade de referência (FR-4 fino)
EPS_R, TAN_D = 4.4, 0.02


class TestCavity:
    def test_f10_hand_value(self):
        """f_10 = c/(2*sqrt(4.4)*0.1 m) = 714.8 MHz (conta de mão)."""
        f = cavity.resonance_freqs(A, B, EPS_R)
        assert f[(1, 0)] == pytest.approx(714.84e6, rel=1e-3)

    def test_mode_ordering(self):
        """Com a > b, f_10 < f_01; f_11 = sqrt(f_10^2 + f_01^2)."""
        f = cavity.resonance_freqs(A, B, EPS_R)
        assert f[(1, 0)] < f[(0, 1)]
        assert f[(1, 1)] == pytest.approx(
            np.hypot(f[(1, 0)], f[(0, 1)]), rel=1e-12)

    def test_low_freq_limit_is_plate_capacitor(self):
        """Em f << f_10, Z(f) -> 1/(jwC) com C = eps*a*b/d exato."""
        f = np.array([1e6, 5e6])
        z = cavity.impedance(f, A, B, D, EPS_R, tan_d=0.0,
                             port_i=(A / 2, B / 2), sigma=1e30)
        c_plate = cavity.EPS0 * EPS_R * A * B / D
        z_cap = 1.0 / (2 * np.pi * f * c_plate)
        assert np.abs(z) == pytest.approx(z_cap, rel=1e-2)

    def test_impedance_peaks_at_resonances(self):
        """Picos de |Z| na porta (a/4, b/4) caem nos f_mn exatos (<1%)."""
        f = np.linspace(100e6, 2.0e9, 4000)
        z = cavity.impedance(f, A, B, D, EPS_R, TAN_D,
                             port_i=(A / 4, B / 4), n_modes=40)
        peaks = cavity.find_peaks_hz(f, np.abs(z))
        f_exact = cavity.resonance_freqs(A, B, EPS_R)
        # cada uma das 3 primeiras ressonâncias tem um pico a <1% dela
        for mode in [(1, 0), (0, 1), (1, 1)]:
            fe = f_exact[mode]
            assert np.min(np.abs(peaks - fe)) / fe < 0.01, \
                f"modo {mode}: sem pico perto de {fe/1e6:.1f} MHz"


# --------------------------------------------------------------- microstrip

class TestMicrostrip:
    def test_air_u1_published(self):
        """Microstrip no ar, w/h = 1: Z0 = 126.4 ohm (H-J 1980)."""
        assert microstrip.z0(1.0, 1.0) == pytest.approx(126.4, abs=1.0)

    def test_eps_eff_bounds(self):
        """1 < eps_eff < eps_r sempre; tende a eps_r p/ trilha larga."""
        for u in [0.1, 1.0, 10.0]:
            ee = microstrip.eps_eff(u, EPS_R)
            assert 1.0 < ee < EPS_R
        assert microstrip.eps_eff(100.0, EPS_R) > 0.9 * EPS_R

    def test_fr4_50ohm_geometry(self):
        """FR-4 (eps_r 4.4), w/h = 2: Z0 = 48.7 ohm (valor de referência
        reproduzido por Qucs/TxLine dentro de ~1 ohm)."""
        assert microstrip.z0(2.0, 4.4) == pytest.approx(48.7, abs=1.0)

    def test_monotonic_in_u(self):
        """Z0 decresce monotonicamente com a largura."""
        u = np.linspace(0.2, 20, 100)
        z = microstrip.z0(u, EPS_R)
        assert np.all(np.diff(z) < 0)


# --------------------------------------------------------------- indutância

class TestInductance:
    def test_wire_1cm_hand_value(self):
        """Fio de 10 mm, raio 0.5 mm: L = 5.88 nH (Rosa, conta de mão)."""
        assert inductance.wire_self(10e-3, 0.5e-3) == \
            pytest.approx(5.878e-9, rel=5e-3)

    def test_square_loop_grover(self):
        """Laço quadrado 10 cm, fio r = 1 mm, via indutâncias parciais,
        contra a forma fechada de Grover:
        L = (2*mu0*a/pi)*(ln(a/r) - 0.77401 + mu_r/4) = 326.5 nH."""
        a, r = 0.1, 1e-3
        l_grover = (2 * inductance.MU0 * a / np.pi) * \
            (np.log(a / r) - 0.77401 + 0.25)
        l_partial = inductance.loop_rect_wire(a, a, r)
        assert l_partial == pytest.approx(l_grover, rel=1e-2)

    def test_bar_vs_wire_consistency(self):
        """Barra quadrada de lado 2r tem L próxima do fio de raio r
        (mesma ordem, diferença < 5%): sanidade entre as duas fórmulas."""
        l, r = 20e-3, 0.5e-3
        lw = inductance.wire_self(l, r)
        lb = inductance.bar_self(l, 2 * r, 2 * r)
        assert abs(lb - lw) / lw < 0.05


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
