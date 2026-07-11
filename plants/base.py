# -*- coding: utf-8 -*-
"""Interface comum entre o algoritmo data-driven (datadriven/) e uma planta,
real (via serial) ou simulada. runner.py so conhece esta interface."""

from abc import ABC, abstractmethod

import numpy as np


class Plant(ABC):
    n: int  # numero de estados
    m: int  # numero de entradas

    @abstractmethod
    def run_experiment(
        self, du: np.ndarray, dt: float, ubar: np.ndarray, settle_s: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Assenta a planta em ubar por settle_s segundos, mede o equilibrio,
        depois aplica ubar + du(k) e coleta a resposta.

        Assentamento e experimento sao uma sequencia atomica (nao dois
        metodos separados): no protocolo serial real o Arduino so aceita GO
        depois de receber o vetor du inteiro, e GO dispara assentamento +
        experimento em uma unica transicao de estados -- nao ha como medir
        o equilibrio sem ja ter committado du.

        du: (m, T) desvios de entrada a aplicar, k = 0..T-1.
        Retorna (ybar, t_raw, y_raw, u_raw):
          ybar (n,)      estado de equilibrio medido;
          t_raw (T+1,)   tempo REAL de cada amostra (s) desde o inicio do
                         experimento -- em plantas seriais e medido no
                         proprio microcontrolador (millis()), permitindo
                         detectar se dt foi de fato alcancado ou se o laco
                         ficou limitado pelo tempo de execucao;
          y_raw (n, T+1) leituras absolutas y(0)..y(T);
          u_raw (m, T)   entrada REALMENTE aplicada (ja com saturacao).
        """

    @abstractmethod
    def run_control(
        self, K: np.ndarray, setpoint: np.ndarray, duration_s: float
    ) -> tuple[list[float], np.ndarray, np.ndarray]:
        """Roda em malha fechada u = ubar + K (y - setpoint), com streaming.

        K: (m, n) ganho data-driven. duration_s == 0 roda indefinidamente
        (ate Ctrl+C / comando de abortar).
        Retorna (t_log, y_log, u_log): y_log (n, N), u_log (m, N).
        """

    @abstractmethod
    def close(self) -> None:
        """Libera recursos (porta serial, etc)."""
