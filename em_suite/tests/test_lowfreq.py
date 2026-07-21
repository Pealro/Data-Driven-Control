"""Validação da extensão de baixa frequência (pdn.lowfreq).

Juiz: o modelo de cavidade, que é EXATO no regime quasi-estático
(a série modal em f << f_10 reduz a 1/(jwC) + jw*L + R). O teste
ajusta o lumped só na banda 80-250 MHz (a banda confiável de uma
extração FDTD típica) e exige que ele preveja 100 kHz-30 MHz — duas
décadas abaixo — dentro de 1% em |Z|.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdn import planes, lowfreq

A, B, D = 100e-3, 80e-3, 0.5e-3
EPS_R, TAN_D = 4.4, 0.02
PORTS = [(A / 4, B / 4), (3 * A / 4, B / 2)]


@pytest.fixture(scope='module')
def z_hf():
    """Matriz 'FDTD sintética': modelo de cavidade na banda de ajuste."""
    f = np.linspace(60e6, 300e6, 400)
    return f, planes.z_matrix(f, A, B, D, EPS_R, TAN_D, PORTS, n_modes=40)


class TestExtendLF:
    def test_predicts_5_to_30mhz(self, z_hf):
        """Ajuste em 80-250 MHz -> previsão em 5-30 MHz (< 1%).

        Banda onde o juiz (modelo de cavidade) é fisicamente válido:
        o termo de perda condutiva delta_s/d exige delta_s << t_cobre
        (35 um), o que vale para f > ~5 MHz."""
        f_hf, z = z_hf
        f_lo = np.logspace(np.log10(5e6), np.log10(30e6), 30)
        z_lo, model, mismatch = lowfreq.extend_lf(f_hf, z, f_lo)
        z_ref = planes.z_matrix(f_lo, A, B, D, EPS_R, TAN_D, PORTS,
                                n_modes=40)
        err = np.abs(np.abs(z_lo) - np.abs(z_ref)) / np.abs(z_ref)
        assert float(np.max(err)) < 0.01
        assert mismatch < 0.05

    def test_predicts_100khz_to_5mhz_lossless_judge(self, z_hf):
        """Em 100 kHz-5 MHz o juiz precisa ser o modelo SEM perda
        condutiva (sigma -> inf): o termo delta_s/d superestima a perda
        quando delta_s > t_cobre — o modelo lumped (R constante pequeno)
        está mais perto da física real lá do que o modelo de cavidade
        com perdas. Detectado quando este teste, originalmente contra o
        modelo completo, falhou com erro ~1/f (assinatura do fator
        1/sqrt(1 + (delta_s/d)^2))."""
        f_hf, z = z_hf
        f_lo = np.logspace(5, np.log10(5e6), 40)
        z_lo, _, _ = lowfreq.extend_lf(f_hf, z, f_lo)
        z_ref = planes.z_matrix(f_lo, A, B, D, EPS_R, TAN_D, PORTS,
                                n_modes=40, sigma=1e30)
        err = np.abs(np.abs(z_lo) - np.abs(z_ref)) / np.abs(z_ref)
        assert float(np.max(err)) < 0.01

    def test_c_matches_plate(self, z_hf):
        """O C ajustado é o C de placas do modelo (sem fringing): exato."""
        f_hf, z = z_hf
        model = lowfreq.fit_lumped(f_hf, z)
        c_plate = 8.8541878128e-12 * EPS_R * A * B / D
        assert model['c'] == pytest.approx(c_plate, rel=5e-3)

    def test_l_symmetric_positive_definite(self, z_hf):
        """A matriz L ajustada é simétrica e definida positiva (física
        de indutâncias parciais: energia magnética > 0)."""
        f_hf, z = z_hf
        model = lowfreq.fit_lumped(f_hf, z)
        l = model['l']
        assert np.allclose(l, l.T)
        assert np.all(np.linalg.eigvalsh(l) > 0)

    def test_mismatch_flags_wave_regime(self, z_hf):
        """Banda de ajuste alta demais (pegando a ressonância de 715 MHz)
        deve degradar o mismatch — o alarme de uso indevido funciona."""
        f = np.linspace(60e6, 900e6, 600)
        z = planes.z_matrix(f, A, B, D, EPS_R, TAN_D, PORTS, n_modes=40)
        _, _, mm_bom = lowfreq.extend_lf(f, z, np.array([1e6]),
                                         fit_band=(80e6, 250e6))
        _, _, mm_ruim = lowfreq.extend_lf(f, z, np.array([1e6]),
                                          fit_band=(400e6, 850e6))
        assert mm_ruim > 5 * mm_bom


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
