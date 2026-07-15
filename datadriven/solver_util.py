# -*- coding: utf-8 -*-
"""Padrao unico de resolucao de LMI do projeto, compartilhado por datadriven/lmi
e koopman/lmi.

Decisoes (medidas nesta maquina, 2026-07-15):
- MOSEK primeiro (licenciado, robusto para estas LMIs), CLARABEL de fallback --
  NAO SCS: o SCS leva ~90 s nestas LMIs (vs ~0,9 s do CLARABEL), virando uma
  armadilha se o MOSEK falhar num ponto.
- verbose do MOSEK vai para um ARQUIVO (log_path), nao para o console: gerar o
  log e barato, mas rola-lo no console do Windows e lento (e o antivirus observa
  cada escrita). Sem log_path -> verbose desligado (rapido e silencioso)."""

import contextlib

import cvxpy as cp


def solve_lmi(problem, log_path=None):
    """Resolve `problem` in-place com o padrao MOSEK->CLARABEL. Se log_path for
    dado, o log verboso do MOSEK e anexado nesse arquivo (fora do console)."""
    if log_path is not None:
        with open(log_path, "a", encoding="utf-8") as log_file:
            with contextlib.redirect_stdout(log_file):
                _solve_mosek_then_clarabel(problem, verbose=True)
    else:
        _solve_mosek_then_clarabel(problem, verbose=False)
    return problem


def _solve_mosek_then_clarabel(problem, verbose):
    try:
        problem.solve(solver=cp.MOSEK, verbose=verbose)
    except Exception:
        problem.solve(solver=cp.CLARABEL)
