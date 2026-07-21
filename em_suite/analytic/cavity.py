"""Modelo de cavidade do par de planos retangular (PDN plane-pair).

Referência: S. Novak / M. Swaminathan, "Power Integrity Modeling and Design
for Semiconductors and Systems"; formulação clássica da série modal dupla
para a impedância de transferência entre duas portas num par de planos
retangular a x b com separação dielétrica d:

    Z_ij(w) = jw*mu*d/(a*b) * sum_{m,n} [ eps_m*eps_n *
              f_mn(x_i,y_i) * f_mn(x_j,y_j) / (k_mn^2 - k^2) ]

    f_mn(x,y) = cos(m*pi*x/a) * cos(n*pi*y/b) * sinc(m*pi*px/(2a)) * sinc(n*pi*py/(2b))

com eps_0 = 1, eps_m = 2 (m > 0), k_mn^2 = (m*pi/a)^2 + (n*pi/b)^2 e
k^2 complexo carregando as perdas dielétrica (tan_d) e condutiva (skin):

    k^2 = w^2 * mu * eps * (1 - j*(tan_d + delta_s/d))

onde delta_s = sqrt(2/(w*mu*sigma)) é a profundidade pelicular do cobre.
As frequências de ressonância exatas (caso sem perdas) são:

    f_mn = c / (2*sqrt(eps_r)) * sqrt((m/a)^2 + (n/b)^2)
"""

import numpy as np

C0 = 299_792_458.0          # m/s
MU0 = 4e-7 * np.pi          # H/m
EPS0 = 1.0 / (MU0 * C0**2)  # F/m
SIGMA_CU = 5.8e7            # S/m


def resonance_freqs(a, b, eps_r, modes=((1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1))):
    """Frequências de ressonância exatas f_mn [Hz] da cavidade a x b [m].

    Retorna dict {(m, n): f_mn} ordenado por frequência crescente.
    """
    out = {}
    for m, n in modes:
        f = C0 / (2.0 * np.sqrt(eps_r)) * np.sqrt((m / a) ** 2 + (n / b) ** 2)
        out[(m, n)] = f
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


def _port_factor(m, n, x, y, px, py, a, b):
    """Fator modal da porta em (x, y) com dimensões px x py."""
    return (np.cos(m * np.pi * x / a) * np.cos(n * np.pi * y / b)
            * np.sinc(m * px / (2.0 * a))     # np.sinc(x) = sin(pi x)/(pi x)
            * np.sinc(n * py / (2.0 * b)))


def impedance(f, a, b, d, eps_r, tan_d, port_i, port_j=None,
              port_size=(0.0, 0.0), sigma=SIGMA_CU, n_modes=30):
    """Z_ij(f) [ohm] do par de planos pelo modelo de cavidade.

    f: array de frequências [Hz]; a, b: dimensões laterais [m];
    d: separação entre planos [m]; port_i/port_j: tuplas (x, y) [m]
    (port_j = port_i dá a impedância própria Z_ii); port_size: (px, py) [m];
    n_modes: índice modal máximo em cada direção (série truncada).
    """
    if port_j is None:
        port_j = port_i
    f = np.asarray(f, dtype=float)
    w = 2.0 * np.pi * f
    xi, yi = port_i
    xj, yj = port_j
    px, py = port_size

    eps = EPS0 * eps_r
    delta_s = np.sqrt(2.0 / (w * MU0 * sigma))
    k2 = w**2 * MU0 * eps * (1.0 - 1j * (tan_d + delta_s / d))

    Z = np.zeros_like(f, dtype=complex)
    for m in range(n_modes + 1):
        for n in range(n_modes + 1):
            eps_mn = (1.0 if m == 0 else 2.0) * (1.0 if n == 0 else 2.0)
            kmn2 = (m * np.pi / a) ** 2 + (n * np.pi / b) ** 2
            num = (eps_mn * _port_factor(m, n, xi, yi, px, py, a, b)
                   * _port_factor(m, n, xj, yj, px, py, a, b))
            Z += num / (kmn2 - k2)
    return 1j * w * MU0 * d / (a * b) * Z


def find_peaks_hz(f, zmag, prominence_rel=2.0):
    """Frequências dos picos de |Z| (ressonâncias) num sweep simulado/medido.

    Pico = máximo local com |Z| pelo menos `prominence_rel` vezes maior que
    os mínimos vizinhos. Retorna array de frequências [Hz].
    """
    from scipy.signal import find_peaks
    zlog = np.log10(np.asarray(zmag))
    idx, _ = find_peaks(zlog, prominence=np.log10(prominence_rel))
    return np.asarray(f)[idx]
