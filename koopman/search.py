# -*- coding: utf-8 -*-
"""Projeto do controlador de Koopman por busca em grade (passo offline).

A LMI (Teorema 4) tem parametros livres -- o peso Rz e os epsilons de folga
numerica. Nem toda combinacao gera um controlador estabilizante na planta real
(a garantia e para o modelo bilinear nominal, nao para o sistema nao-linear
verdadeiro). Entao varremos uma grade, simulamos cada candidato em malha fechada
e escolhemos o que mais aproxima o estado da origem -- mesma estrategia
'projeta-e-simula' do notebook (buscar_controladores_lmi)."""

import numpy as np

from koopman.lmi import solve_koopman_lmi

# grades que funcionaram no notebook para o Van der Pol (Phi/monomios)
GRID_RZ_PADRAO = [1e-8, 3e-8, 1e-7, 3e-7, 1e-6, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2]
GRID_EPS_PADRAO = [
    {"eps_P": 1e-9, "eps_Lambda": 1e-9, "eps_nu": 1e-9, "eps_F": 0.0},
    {"eps_P": 1e-10, "eps_Lambda": 1e-10, "eps_nu": 1e-10, "eps_F": 1e-10},
    {"eps_P": 1e-9, "eps_Lambda": 1e-9, "eps_nu": 1e-9, "eps_F": 1e-9},
]


def design_controller(
    A, B0, B1, simulate_fn,
    grid_Rz=GRID_RZ_PADRAO, grid_eps=GRID_EPS_PADRAO, solver=None, verbose=True,
):
    """Varre (Rz, eps), resolve a LMI, simula com simulate_fn(K, Kw) e escolhe o
    de menor norma final do estado.

    simulate_fn(K, Kw) -> (score, info): score menor = melhor; info livre (dict).
    O chamador injeta a simulacao (assim koopman/ nao depende de plants/).

    Retorna (melhor, candidatos) onde cada item e
    {"res": <saida da LMI>, "score": float, "info": ...}.
    """
    candidatos = []
    for eps_cfg in grid_eps:
        for Rz in grid_Rz:
            res = solve_koopman_lmi(A, B0, B1, Rz, solver=solver, **eps_cfg)
            if not res["sucesso"]:
                continue
            score, info = simulate_fn(res["K"], res["Kw"])
            candidatos.append({"res": res, "score": float(score), "info": info})
            if verbose:
                print(
                    f"    Rz={Rz:.1e} eps_F={eps_cfg['eps_F']:.1e} | "
                    f"score={score:.3e} cond(P)={res['condP']:.2e}"
                )
    if not candidatos:
        raise RuntimeError(
            "Nenhuma solucao de LMI viavel -- verifique o solver (Koopman "
            "precisa de MOSEK; CLARABEL/SCS costumam falhar nestas LMIs)."
        )
    melhor = min(candidatos, key=lambda c: c["score"])
    return melhor, candidatos
