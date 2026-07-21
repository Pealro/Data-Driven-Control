"""Referências analíticas para validação de solvers EM (Fase 1 da suíte).

Cada submódulo implementa fórmulas de forma fechada com resposta exata
conhecida, usadas como âncora de validação para openEMS/FastHenry:

- cavity: ressonâncias e Z(f) do par de planos (modelo de cavidade)
- microstrip: Z0 e eps_eff por Hammerstad-Jensen
- inductance: indutância parcial de condutores retos (Rosa/Grover)
"""

from . import cavity, microstrip, inductance

__all__ = ["cavity", "microstrip", "inductance"]
