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
        self,
        T: int,
        dt: float,
        ubar: np.ndarray,
        settle_s: float,
        amp_entrada: float,
        seed: int | None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Assenta a planta em ubar por settle_s segundos, mede o equilibrio,
        depois aplica T passos de ubar + du(k) ~ U(-amp_entrada, amp_entrada)
        e coleta a resposta.

        A geracao de du(k) e responsabilidade de CADA implementacao de
        Plant, nao do chamador: uma planta serial manda a semente ao
        firmware e ele gera du(k) sob demanda (sem guardar o vetor inteiro
        em RAM -- ver plants/serial_plant.py); a planta simulada gera du
        localmente em Python (datadriven.excitation). Isso evita que T seja
        limitado pela RAM de um microcontrolador real.

        Assentamento e experimento sao uma sequencia atomica (nao dois
        metodos separados): no protocolo serial real o Arduino so aceita GO
        apos CFG, e GO dispara assentamento + experimento em uma unica
        transicao de estados.

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
