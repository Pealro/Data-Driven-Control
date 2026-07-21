"""Extensão de baixa frequência para matrizes Z extraídas por FDTD.

CONTEXTO: a extração FDTD (extract_openems) tem piso útil f_min de
algumas unidades de 1/T_janela (~60-80 MHz com janela de ~150 ns) —
limitação da SIMULAÇÃO, não da física. Abaixo da primeira ressonância
o par de planos é quasi-estático:

    Z_ij(w) = R_ij + 1/(jwC) + jw*L_ij

com C ÚNICO para todas as entradas (termo monopolo, modo (0,0) — o
mesmo para qualquer par de portas) e L_ij a matriz de indutâncias
parciais de espalhamento. Nesse regime a forma fechada é exata; FDTD
só é necessário onde há efeitos de onda.

Este módulo ajusta (C, L_ij, R_ij) na banda CONFIÁVEL do FDTD e gera
Z em qualquer frequência abaixo dela — cobrindo os sinais de interesse
comuns em PDN (chaveamento de DC-DC 100 kHz-2 MHz, envelope de burst
GSM, harmônicos baixos) para geometria que o modelo de cavidade não
cobre (fendas, recortes).

Validação: teste com o modelo de cavidade como entrada (ajuste em
80-250 MHz, previsão em 0.1-30 MHz, comparação com o próprio modelo,
que é exato em LF) — ver tests/test_lowfreq.py.
"""

import numpy as np


def fit_lumped(f, z, f0=80e6, f1=250e6):
    """Ajusta o modelo quasi-estático na banda [f0, f1].

    f: (F,) Hz; z: (F, N, N) complexo.
    Retorna dict {c, l (N,N), r (N,N)}. Unidades normalizadas (Grad/s)
    no lstsq — sem isso a coluna capacitiva é descartada por escala.
    """
    z = np.asarray(z)
    n = z.shape[1]
    m = (f >= f0) & (f <= f1)
    wg = 2.0 * np.pi * f[m] / 1e9

    # C compartilhado: ajuste na entrada (0, 0)
    a_mat = np.column_stack([-1.0 / wg, wg])
    coef, *_ = np.linalg.lstsq(a_mat, z[m, 0, 0].imag, rcond=None)
    c = 1e-9 / coef[0]

    # L_ij com C fixo; R_ij = média de Re na banda
    w = 2.0 * np.pi * f[m]
    l = np.empty((n, n))
    r = np.empty((n, n))
    for i in range(n):
        for j in range(n):
            l[i, j] = float(np.mean((z[m, i, j].imag + 1.0 / (w * c)) / w))
            r[i, j] = float(np.mean(z[m, i, j].real))
    # simetriza (rede recíproca)
    l = 0.5 * (l + l.T)
    r = 0.5 * (r + r.T)
    return {'c': c, 'l': l, 'r': r}


def z_lumped(f, model):
    """Z (F, N, N) do modelo quasi-estático em frequências f [Hz]."""
    f = np.asarray(f, dtype=float)
    w = 2.0 * np.pi * f
    c, l, r = model['c'], model['l'], model['r']
    n = l.shape[0]
    z = np.empty((len(f), n, n), dtype=complex)
    z_c = 1.0 / (1j * w * c)
    for i in range(n):
        for j in range(n):
            z[:, i, j] = r[i, j] + z_c + 1j * w * l[i, j]
    return z


def extend_lf(f_fdtd, z_fdtd, f_lf, fit_band=(80e6, 250e6)):
    """Matriz Z na grade f_lf (abaixo do piso FDTD) via modelo ajustado.

    Retorna (z_lf, model, mismatch_im): mismatch_im é o erro relativo
    mediano da parte IMAGINÁRIA, |Im{Z_model - Z_fdtd}|/|Im{Z_fdtd}|,
    na banda de ajuste — mede se o regime lá ainda é quasi-estático
    (reatância = -1/(wC) + wL). Se alto, a banda pegou efeitos de onda.

    A métrica ignora deliberadamente a parte Real: em LF, Re{Z} do
    FDTD é pequena e sai corrompida pelo leakage da janela finita
    (medido: Re inflado ~6x a 80 MHz vs modelo de cavidade), por igual
    em qualquer geometria. O R do modelo (model['r']) é reportado, mas
    para resistência de planos em LF a fonte correta é um solver DC
    (IR drop) — não o FDTD.

    Escolha de fit_band: piso ~80 MHz (qualidade da DFT com janela
    ~150 ns); teto ~metade da primeira ressonância da ESTRUTURA (o
    regime quasi-estático é dela, não um número fixo — um plano com
    fenda ressoa mais baixo que o intacto).
    """
    model = fit_lumped(f_fdtd, z_fdtd, *fit_band)
    m = (f_fdtd >= fit_band[0]) & (f_fdtd <= fit_band[1])
    z_fit = z_lumped(f_fdtd[m], model)
    mismatch_im = float(np.median(
        np.abs(z_fit.imag - z_fdtd[m].imag) / np.abs(z_fdtd[m].imag)))
    return z_lumped(f_lf, model), model, mismatch_im
