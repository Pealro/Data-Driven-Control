"""Indutância parcial de condutores retos — fórmulas de Rosa/Grover/Ruehli.

Referências: E. B. Rosa, "The self and mutual inductances of linear
conductors" (NBS, 1908); F. W. Grover, "Inductance Calculations" (1946);
A. E. Ruehli, "Inductance calculations in a complex integrated circuit
environment" (IBM JRD, 1972). Baixa frequência (corrente uniforme).
"""

import numpy as np

MU0 = 4e-7 * np.pi  # H/m


def wire_self(l, r):
    """Indutância parcial própria [H] de fio cilíndrico: comprimento l, raio r [m].

    L = (mu0*l/2pi) * [ln(2l/r) - 1 + mu_r/4], com mu_r = 1 (não magnético).
    Válida para l >> r.
    """
    return MU0 * l / (2.0 * np.pi) * (np.log(2.0 * l / r) - 0.75)


def bar_self(l, w, t):
    """Indutância parcial própria [H] de barra retangular l x w x t [m].

    Aproximação de Ruehli/Rosa para barra fina:
    L = (mu0*l/2pi) * [ln(2l/(w+t)) + 0.5 + 0.2235*(w+t)/l]
    Válida para l >> (w + t).
    """
    return MU0 * l / (2.0 * np.pi) * (np.log(2.0 * l / (w + t)) + 0.5
                                      + 0.2235 * (w + t) / l)


def wires_mutual(l, s):
    """Indutância parcial mútua [H] entre dois filamentos paralelos de
    comprimento l separados por s [m] — forma exata de Rosa/Grover:

    M = (mu0*l/2pi) * [asinh(l/s) - sqrt(1 + (s/l)^2) + s/l]
    """
    return MU0 * l / (2.0 * np.pi) * (np.arcsinh(l / s)
                                      - np.sqrt(1.0 + (s / l) ** 2) + s / l)


def loop_rect_wire(a, b, r):
    """Indutância [H] de laço retangular a x b de fio com raio r [m].

    Forma fechada de Grover (laço de fio fino, mu_r = 1):
    L = (mu0/pi) * [ a*ln(2ab/(r*(a+g))) + b*ln(2ab/(r*(b+g)))
                     + 2g - 2(a+b) + (a+b)*... ]
    Implementada na forma padrão:
    L = (mu0/pi) * [ a*asinh(a/b) + b*asinh(b/a) - a*... ]

    Usa-se aqui a expressão exata por indutâncias parciais:
    L = 2*(Lp_a + Lp_b) - 2*(M_a + M_b), onde Lp é a autoindutância parcial
    de cada lado e M a mútua entre lados opostos (separados por b e a).
    """
    lp_a = wire_self(a, r)
    lp_b = wire_self(b, r)
    m_a = wires_mutual(a, b)   # lados de comprimento a, separados por b
    m_b = wires_mutual(b, a)
    return 2.0 * (lp_a + lp_b) - 2.0 * (m_a + m_b)
