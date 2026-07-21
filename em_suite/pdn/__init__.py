"""Pipeline PDN AC (Fase 2) — equivalente open source do fluxo PIPro.

Monta a impedância Z(f) vista pelo chip num rail de alimentação:

1. planes: matriz Z multiporta do par de planos (modelo de cavidade,
   validado no caso 1 contra openEMS);
2. capacitor: modelo RLC série dos capacitores de desacoplamento
   (C, ESR, ESL de datasheet + indutância de montagem);
3. network: redução de rede (complemento de Schur) — capacitores como
   cargas shunt nas portas, Zin nas portas do chip;
4. target: impedância-alvo a partir do transiente de corrente.

Validação: caso 4 (cross-check contra openEMS com elemento lumped).
"""

from . import planes, capacitor, network, target

__all__ = ["planes", "capacitor", "network", "target"]
