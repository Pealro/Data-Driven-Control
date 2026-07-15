# -*- coding: utf-8 -*-
"""Simulacao da malha fechada no MODELO bilinear identificado (z+ = A z +
u(B0 + B1 z)). Usado na busca de controlador (koopman/search) quando a planta
NAO pode ser simulada de verdade -- caso do hardware real: nao da para rodar 30
candidatos no Arduino, entao a selecao e feita offline no modelo (que foi
identificado dos dados reais, entao um controlador que estabiliza o modelo
robusto estabiliza a planta -- e a garantia da LMI).

Para a planta simulada (Van der Pol) preferimos rollout na dinamica verdadeira
(plant.rollout), que reproduz o notebook; este model_rollout e o fallback."""

import numpy as np


def model_rollout(A, B0, B1, compute_u, exponents, x0, n_state, n_steps):
    """Roda z+ = A z + u(B0 + B1 z) em malha fechada, u=compute_u(x) com
    x = z[:n_state] (os n_state primeiros monomios sao o estado fisico, ver
    koopman/lifting.monomial_exponents). Retorna dict com X (n_steps+1, n_state)
    e flag de explosao -- mesma interface parcial de VanDerPolPlant.rollout."""
    from koopman.lifting import phi_vector

    A = np.asarray(A, dtype=float)
    B0 = np.asarray(B0, dtype=float).reshape(-1, 1)
    B1 = np.asarray(B1, dtype=float)

    x = np.asarray(x0, dtype=float).reshape(n_state)
    X = np.zeros((n_steps + 1, n_state))
    X[0, :] = x
    explodiu, motivo = False, "ok"
    for k in range(n_steps):
        try:
            u = float(compute_u(x))
        except Exception as erro:
            X[k + 1:, :] = np.nan
            explodiu, motivo = True, str(erro)
            break
        # REELEVA z=Phi(x) a cada passo (projeta na variedade dos monomios),
        # espelhando o hardware: mede-se x e recalcula-se z. Propagar o z
        # elevado sem reprojetar deixa z sair da variedade e distorce a
        # predicao. O modelo bilinear preve so o proximo estado fisico x.
        z = phi_vector(x, exponents).reshape(-1, 1)
        z_next = A @ z + u * (B0 + B1 @ z)
        x = z_next[:n_state, 0]
        if not np.all(np.isfinite(x)) or np.linalg.norm(x) > 1e8:
            X[k + 1:, :] = np.nan
            explodiu, motivo = True, "estado explodiu"
            break
        X[k + 1, :] = x
    return {"X": X, "explodiu": explodiu, "motivo": motivo}
