# -*- coding: utf-8 -*-
"""Montagem de X0, X1, U0 (desvios em torno do equilibrio) a partir dos
dados brutos coletados na planta. Agnostico de n (estados) e m (entradas).

Suporta embutimento de atraso (delay-embedding, parametro L): quando a ordem
verdadeira da planta e maior que o numero de sensores, o estado medido y nao e
o estado completo. Empilhar L amostras de y e u recupera um estado valido
(realizacao ARX / estado comportamental de Willems) que satisfaz a mesma
relacao linear x~(k+1) = A x~(k) + B u(k), alimentando a MESMA LMI de De Persis
& Tesi. L=1 e byte-a-byte identico ao metodo original."""

import numpy as np


def embedded_state_dim(n: int, m: int, L: int) -> int:
    """Dimensao do estado aumentado x~ = [y(k)..y(k-L+1), u(k-1)..u(k-L+1)].
    L=1 -> n (sem atraso, estado = y). L>1 -> L*n + (L-1)*m."""
    return L * n + (L - 1) * m


def build_X0_X1_U0(
    y_raw: np.ndarray,
    u_raw: np.ndarray,
    ybar: np.ndarray,
    ubar: np.ndarray,
    L: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    y_raw : (n, T+1) leituras absolutas de estado, incluindo o equilibrio -- y(0)..y(T)
    u_raw : (m, T)   entrada REALMENTE aplicada (ja com saturacao) -- u(0)..u(T-1)
    ybar  : (n,)     estado de equilibrio medido
    ubar  : (m,)     entrada de equilibrio
    L     : profundidade do embutimento de atraso (1 = sem embutimento)

    Retorna X0 (n_eff,T'), X1 (n_eff,T'), U0 (m,T') -- notacao de X_{0,T},
    X_{1,T}, U_{0,1,T} do artigo (De Persis & Tesi, 2020, eq. 51, Teorema 6),
    com n_eff = embedded_state_dim(n,m,L).

    Com L=1: X0 (n,T), X1 (n,T), U0 (m,T) -- identico ao original.
    Com L>1: o estado aumentado no instante k e
        x~(k) = [dy(k), dy(k-1), ..., dy(k-L+1), du(k-1), ..., du(k-L+1)]
    (desvios em torno do equilibrio), definido para k = L-1 .. T-1; entao
    T' = T - L + 1 colunas. As primeiras n linhas de x~ sao o estado fisico
    atual dy(k), como no caso L=1.
    """
    n, sample_count = y_raw.shape  # sample_count = T + 1 (inclui o estado inicial)
    T = sample_count - 1
    m = u_raw.shape[0]
    dy = y_raw - ybar.reshape(n, 1)          # (n, T+1)
    du = u_raw - ubar.reshape(m, 1)          # (m, T)

    if L == 1:
        return dy[:, 0:T], dy[:, 1:T + 1], du[:, 0:T]

    if L < 1:
        raise ValueError(f"L deve ser >= 1, recebido {L}")
    if T < L:
        raise ValueError(f"T={T} amostras insuficientes para embutimento L={L}")

    def x_tilde(k: int) -> np.ndarray:
        # [dy(k)..dy(k-L+1)] (L blocos de n) + [du(k-1)..du(k-L+1)] (L-1 blocos de m)
        y_blocos = [dy[:, k - i] for i in range(L)]
        u_blocos = [du[:, k - 1 - i] for i in range(L - 1)]
        return np.concatenate(y_blocos + u_blocos)

    cols_0 = range(L - 1, T)          # k = L-1 .. T-1  -> x~(k)
    X0 = np.column_stack([x_tilde(k) for k in cols_0])
    X1 = np.column_stack([x_tilde(k + 1) for k in cols_0])
    U0 = np.column_stack([du[:, k] for k in cols_0])
    return X0, X1, U0
