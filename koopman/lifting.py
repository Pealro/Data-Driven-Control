# -*- coding: utf-8 -*-
"""Lifting Phi de Koopman por monomios (Carleman): z = Phi(x) empilha todos os
monomios x1^a1 * ... * xn^an de grau total 1..grau_maximo (SEM termo constante,
para que Phi(0) = 0 -- a origem do estado vira a origem do espaco elevado, que e
o ponto que o controlador estabiliza)."""

import numpy as np


def monomial_exponents(n: int, grau_maximo: int = 5) -> np.ndarray:
    """Expoentes (n,) de cada monomio de grau total 1..grau_maximo em n
    variaveis. Retorna (N_phi, n) inteiro.

    Ordem: por grau crescente; dentro do grau, primeiro expoente descendente
    (recursivamente). Para n=2 reproduz exatamente o gerar_expoentes_monomiais
    do notebook ((1,0),(0,1),(2,0),(1,1),(0,2),...). Consequencia importante: os
    n PRIMEIROS monomios sao os de grau 1 na ordem identidade (x1, x2, ..., xn),
    entao z[0:n] = estado fisico x -- varios pontos do pipeline contam com isso."""
    exps = []

    def recurse(prefix, restantes, grau_alvo):
        if restantes == 1:
            exps.append(prefix + [grau_alvo])
            return
        for e in range(grau_alvo, -1, -1):  # descendente: casa com a ordem do notebook
            recurse(prefix + [e], restantes - 1, grau_alvo - e)

    for grau in range(1, grau_maximo + 1):
        recurse([], n, grau)
    return np.array(exps, dtype=int)


def phi(X: np.ndarray, exponents: np.ndarray) -> np.ndarray:
    """Aplica o lifting as colunas de X.

    X          : (n, M) -- M estados de dimensao n
    exponents  : (N_phi, n)
    retorna    : (N_phi, M)

    Vetorizado (broadcasting) em vez do laco por coluna do notebook -- importa
    porque phi e avaliado a CADA passo no laco de controle.
    """
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.shape[0] != exponents.shape[1]:
        raise ValueError(
            f"X tem {X.shape[0]} estados mas exponents espera {exponents.shape[1]}"
        )
    # X[None,:,:] (1,n,M) ** exponents[:,:,None] (N_phi,n,1) -> (N_phi,n,M);
    # produto sobre o eixo dos estados -> (N_phi, M)
    return np.prod(X[None, :, :] ** exponents[:, :, None], axis=1)


def phi_vector(x: np.ndarray, exponents: np.ndarray) -> np.ndarray:
    """Conveniencia: Phi de um unico estado x (n,) -> z (N_phi,)."""
    return phi(np.asarray(x, dtype=float).reshape(-1, 1), exponents)[:, 0]
