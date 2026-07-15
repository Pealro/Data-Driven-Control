# -*- coding: utf-8 -*-
"""Controle com modelo de Koopman (Strasser, Berberich, Allgower, IFAC 2023):
lifting Phi (monomios) -> EDMD bilinear (z+ = A z + u(B0 + B1 z)) -> LMI robusta
(Teorema 4 nominal, entrada escalar m=1) -> controlador racional u = (Kz)/(1-Kw z).

Pacote paralelo ao datadriven/ (De Persis & Tesi): mesma ideia de "identificar o
controlador direto dos dados", mas para plantas NAO-lineares via operador de
Koopman. So suporta m=1 (o artigo e escalar-input; MIMO e trabalho futuro)."""
