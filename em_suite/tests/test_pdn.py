"""Testes do pipeline PDN contra limites exatos e identidades de rede.

Rodar: python -m pytest em_suite/tests -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytic import cavity
from pdn import planes, network, target
from pdn.capacitor import Decap, DecapS2P

A, B, D = 100e-3, 80e-3, 0.5e-3
EPS_R, TAN_D = 4.4, 0.02
P_CHIP = (A / 4, B / 4)
P_CAP = (3 * A / 4, B / 2)
F = np.linspace(10e6, 1.5e9, 800)


@pytest.fixture(scope='module')
def zmat():
    return planes.z_matrix(F, A, B, D, EPS_R, TAN_D, [P_CHIP, P_CAP])


class TestPlanesMatrix:
    def test_diagonal_matches_cavity_impedance(self, zmat):
        """Z11 da matriz multiporta == cavity.impedance (mesma série)."""
        z11 = cavity.impedance(F, A, B, D, EPS_R, TAN_D, port_i=P_CHIP,
                               port_size=(1e-3, 1e-3), n_modes=30)
        assert np.allclose(zmat[:, 0, 0], z11, rtol=1e-10)

    def test_reciprocity(self, zmat):
        """Rede recíproca: Z12 == Z21 exatamente."""
        assert np.allclose(zmat[:, 0, 1], zmat[:, 1, 0], rtol=1e-12)

    def test_passivity(self, zmat):
        """Rede passiva com perdas: Re{Z11} > 0 e Re{Z22} > 0 em toda
        a banda (identidade física rigorosa, ao contrário de qualquer
        relação entre |Z12| e |Z11|, que não é garantida)."""
        assert np.all(zmat[:, 0, 0].real > 0)
        assert np.all(zmat[:, 1, 1].real > 0)


class TestNetworkReduction:
    def test_no_load_is_identity(self, zmat):
        """Sem cargas, Zin == Z11 puro."""
        zin = network.z_in(F, zmat, 0, {})
        assert np.allclose(zin, zmat[:, 0, 0], rtol=1e-12)

    def test_short_at_port2_schur_formula(self, zmat):
        """Curto ideal na porta 2: Zin = Z11 - Z12^2/Z22 (forma fechada)."""
        class Short:
            def z(self, f):
                return np.zeros(len(f), dtype=complex)
        zin = network.z_in(F, zmat, 0, {1: Short()})
        expected = (zmat[:, 0, 0]
                    - zmat[:, 0, 1] * zmat[:, 1, 0] / zmat[:, 1, 1])
        assert np.allclose(zin, expected, rtol=1e-10)

    def test_decap_dominates_low_freq(self):
        """Em f muito baixa (10-50 kHz), |Zin| == |Z_cap| a < 0.5%: os
        planos contribuem só ~0.95 nH de espalhamento entre as portas
        (medido no próprio modelo: Zin - Zcap = jw*L_spread), que aqui
        pesa < 0.05%. Nota: a 250 kHz esse mesmo 1 nH já desvia 2.4%,
        porque |Zcap| do 10 uF cai para ~60 mohm perto da SRF montada."""
        f_lo = np.linspace(10e3, 50e3, 30)
        zm = planes.z_matrix(f_lo, A, B, D, EPS_R, TAN_D, [P_CHIP, P_CAP])
        cap = Decap(c=10e-6, esr=5e-3, esl=1e-9, l_mnt=0.5e-9)
        zin = network.z_in(f_lo, zm, 0, {1: cap})
        assert np.abs(zin) == pytest.approx(np.abs(cap.z(f_lo)), rel=5e-3)

    def test_spreading_inductance_positive_and_small(self):
        """O resíduo Zin - Zcap é indutivo (Im > 0, ~constante em f) e da
        ordem de 1 nH nesta geometria — sanidade física do espalhamento
        entre portas."""
        f_lo = np.array([100e3, 200e3, 400e3])
        zm = planes.z_matrix(f_lo, A, B, D, EPS_R, TAN_D, [P_CHIP, P_CAP])
        cap = Decap(c=10e-6, esr=5e-3, esl=1e-9, l_mnt=0.5e-9)
        zin = network.z_in(f_lo, zm, 0, {1: cap})
        l_spread = (zin - cap.z(f_lo)).imag / (2 * np.pi * f_lo)
        assert np.all((l_spread > 0.2e-9) & (l_spread < 3e-9))
        assert np.ptp(l_spread) / np.mean(l_spread) < 0.1

    def test_mounted_srf_formula(self):
        """SRF montada do Decap segue 1/(2*pi*sqrt(LC)) exato."""
        cap = Decap(c=100e-9, esr=20e-3, esl=0.6e-9, l_mnt=0.4e-9)
        assert cap.srf() == pytest.approx(
            1.0 / (2 * np.pi * np.sqrt(1e-9 * 100e-9)), rel=1e-12)

    def test_antiresonance_between_two_caps(self):
        """Dois decaps de valores diferentes criam anti-ressonância entre
        as SRFs: o pico de |Zin| fica entre f_s1 e f_s2 — o fenômeno que
        o PDN Analyzer DC não enxerga."""
        f = np.linspace(1e6, 200e6, 4000)
        zm = planes.z_matrix(f, A, B, D, EPS_R, TAN_D,
                             [P_CHIP, P_CAP, (A / 2, 3 * B / 4)])
        c_big = Decap(c=1e-6, esr=10e-3, esl=1e-9, l_mnt=0.5e-9)
        c_small = Decap(c=10e-9, esr=20e-3, esl=0.6e-9, l_mnt=0.4e-9)
        zin = network.z_in(f, zm, 0, {1: c_big, 2: c_small})
        band = (f > c_big.srf()) & (f < c_small.srf())
        i_pk = np.argmax(np.abs(zin[band]))
        z_pk = np.abs(zin[band])[i_pk]
        # pico existe e excede a impedância nas duas SRFs
        i1 = np.argmin(np.abs(f - c_big.srf()))
        i2 = np.argmin(np.abs(f - c_small.srf()))
        assert z_pk > 3 * np.abs(zin[i1])
        assert z_pk > 3 * np.abs(zin[i2])


class TestDecapS2P:
    @staticmethod
    def _write_s2p(path, cap, f, mode):
        """Sintetiza um touchstone S2P do RLC dado, na convenção pedida."""
        z0 = 50.0
        zd = cap.z(f)
        if mode == 'series':
            s21 = 2 * z0 / (2 * z0 + zd)
            s11 = zd / (zd + 2 * z0)
        else:  # shunt
            zp = zd
            s21 = 2 * zp / (2 * zp + z0)
            s11 = -z0 / (2 * zp + z0)
        with open(path, 'w') as fh:
            fh.write('# Hz S RI R 50\n')
            for k in range(len(f)):
                fh.write(f'{f[k]:.6e} {s11[k].real:.9e} {s11[k].imag:.9e} '
                         f'{s21[k].real:.9e} {s21[k].imag:.9e} '
                         f'{s21[k].real:.9e} {s21[k].imag:.9e} '
                         f'{s11[k].real:.9e} {s11[k].imag:.9e}\n')

    @pytest.mark.parametrize('mode', ['series', 'shunt'])
    def test_roundtrip_rlc(self, tmp_path, mode):
        """S2P sintetizado de um RLC conhecido -> DecapS2P recupera a
        mesma Z(f) (< 0.1%), nas duas convenções de medição."""
        rlc = Decap(c=100e-9, esr=20e-3, esl=1e-9, l_mnt=0.0)
        f_file = np.logspace(5, 9.3, 400)
        p = tmp_path / 'cap.s2p'
        self._write_s2p(p, rlc, f_file, mode)
        s2p = DecapS2P(path=p, l_mnt=0.0, mode=mode)
        f = np.logspace(5.1, 9.2, 100)
        assert np.abs(s2p.z(f)) == pytest.approx(np.abs(rlc.z(f)), rel=1e-3)

    def test_no_extrapolation(self, tmp_path):
        """Fora da banda do arquivo: erro, nunca extrapolação."""
        rlc = Decap(c=100e-9)
        f_file = np.linspace(1e6, 1e9, 50)
        p = tmp_path / 'cap.s2p'
        self._write_s2p(p, rlc, f_file, 'series')
        s2p = DecapS2P(path=p, l_mnt=0.0)
        with pytest.raises(ValueError, match='fora do S2P'):
            s2p.z(np.array([1e5, 1e6]))

    def test_l_mnt_adds(self, tmp_path):
        """l_mnt desloca a SRF para baixo como no RLC equivalente."""
        rlc = Decap(c=100e-9, esr=20e-3, esl=1e-9, l_mnt=0.5e-9)
        rlc_semmnt = Decap(c=100e-9, esr=20e-3, esl=1e-9, l_mnt=0.0)
        f_file = np.logspace(5, 9.3, 800)
        p = tmp_path / 'cap.s2p'
        self._write_s2p(p, rlc_semmnt, f_file, 'series')
        s2p = DecapS2P(path=p, l_mnt=0.5e-9)
        f = np.logspace(6, 9, 2000)
        f_dip_s2p = f[np.argmin(np.abs(s2p.z(f)))]
        f_dip_rlc = f[np.argmin(np.abs(rlc.z(f)))]
        assert f_dip_s2p == pytest.approx(f_dip_rlc, rel=0.01)


class TestTarget:
    def test_flat_value(self):
        """Rail 3.8 V, ripple 3%, burst 2 A: Zt = 57 mohm."""
        assert target.target_z(3.8, 0.03, 2.0) == pytest.approx(0.057)

    def test_violations_segments(self):
        """violations() reporta exatamente a sub-banda excedida."""
        f = np.array([1., 2., 3., 4., 5.])
        z = np.array([0.5, 1.5, 2.0, 0.5, 0.5])
        v = target.violations(f, z, np.ones(5))
        assert len(v) == 1
        assert v[0][0] == 2. and v[0][1] == 3. and v[0][2] == 2.0


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
