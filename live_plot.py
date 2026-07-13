# -*- coding: utf-8 -*-
"""Plots ao vivo (Bloco B: aquisicao; Bloco D: controle). Atualiza em
throttle de tempo (nao a cada amostra) para nao comprometer o dt medido
durante a coleta -- o mesmo cuidado que ja tomamos com a precisao do
timestamp do firmware nesta sessao."""

import time
from collections import deque
from itertools import chain

import matplotlib
import numpy as np

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

CONTROL_PLOT_WINDOW_SIZE = 1000  # janela deslizante (Bloco D): mantem as ultimas
# 1000 amostras no grafico e desliza a partir dai -- o CSV salvo continua com
# o historico completo (t_log/y_log/u_log vem de plant.run_control, nao destes
# buffers de plot)

ACQUISITION_PLOT_WINDOW_SIZE = 1000  # janela deslizante (Bloco B), mesmo raciocinio


class LiveAcquisitionPlot:
    """3 paineis: entrada u(t), saida y(t), distribuicao (histograma) de u
    coletado ate agora. Label no canto superior mostra quantas amostras
    faltam coletar (T e conhecido de antemao, vem do wizard)."""

    def __init__(
        self,
        plant_name: str,
        n: int,
        m: int,
        T: int,
        # folga extra em relacao ao antigo 0.2s -- headroom para o pior
        # caso de m=4,n=4 (8 linhas + histograma), mesmo raciocinio do
        # throttle do Bloco D: redraw() nao pode competir com a leitura da
        # serial.
        refresh_interval_s: float = 0.3,
        window_size: int = ACQUISITION_PLOT_WINDOW_SIZE,
    ):
        self.n = n
        self.m = m
        self.T = T
        self.refresh_interval_s = refresh_interval_s
        self._last_refresh = 0.0
        self._sample_count = 0

        self.t_buf: deque[float] = deque(maxlen=window_size)
        self.y_buf: list[deque[float]] = [deque(maxlen=window_size) for _ in range(n)]
        self.u_buf: list[deque[float]] = [deque(maxlen=window_size) for _ in range(m)]

        plt.ion()
        self.fig, (self.ax_u, self.ax_y, self.ax_hist) = plt.subplots(
            3, 1, figsize=(9, 10), constrained_layout=True
        )
        self.fig.suptitle(f"Aquisicao ao vivo -- {plant_name}")
        self._remaining_label = self.fig.text(
            0.99, 0.995, "", ha="right", va="top", fontsize=10,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

        self.u_lines = [self.ax_u.plot([], [], label=f"u{j + 1}")[0] for j in range(m)]
        self.ax_u.set_title("Entrada u(t)")
        self.ax_u.set_xlabel("tempo [s]")
        self.ax_u.legend(loc="upper right")
        self.ax_u.grid(alpha=0.3)

        self.y_lines = [self.ax_y.plot([], [], label=f"y{i + 1}")[0] for i in range(n)]
        self.ax_y.set_title("Saida y(t)")
        self.ax_y.set_xlabel("tempo [s]")
        self.ax_y.legend(loc="upper right")
        self.ax_y.grid(alpha=0.3)

        self.ax_hist.set_title("Distribuicao de u coletado")
        self.ax_hist.grid(alpha=0.3)

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def add_sample(self, t_s: float, y_vals, u_vals) -> None:
        self.t_buf.append(t_s)
        for i in range(self.n):
            self.y_buf[i].append(float(y_vals[i]))
        for j in range(self.m):
            self.u_buf[j].append(float(u_vals[j]))
        self._sample_count += 1

        now = time.monotonic()
        if now - self._last_refresh < self.refresh_interval_s:
            return
        self._last_refresh = now
        self.redraw()

    def redraw(self) -> None:
        for j, line in enumerate(self.u_lines):
            line.set_data(self.t_buf, self.u_buf[j])
        self.ax_u.relim()
        self.ax_u.autoscale_view()

        for i, line in enumerate(self.y_lines):
            line.set_data(self.t_buf, self.y_buf[i])
        self.ax_y.relim()
        self.ax_y.autoscale_view()

        self.ax_hist.cla()
        # np.fromiter + itertools.chain em vez de list comprehension
        # aninhada -- mais rapido para achatar m canais * ate window_size
        # amostras cada (relevante com m=4, o maximo suportado pela planta
        # generica) sem crescer o custo por causa da quantidade de canais
        all_u = np.fromiter(chain.from_iterable(self.u_buf), dtype=float)
        if all_u.size:
            self.ax_hist.hist(all_u, bins=20, color="tab:red", alpha=0.75)
        self.ax_hist.set_title("Distribuicao de u coletado")
        self.ax_hist.grid(alpha=0.3)

        remaining = max(0, self.T - self._sample_count)
        self._remaining_label.set_text(f"faltam {remaining}/{self.T} amostras")

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self, keep_open: bool = False, save_path: str | None = None) -> None:
        self.redraw()  # garante que o estado final (todas as amostras) aparece
        if save_path:
            self.fig.savefig(save_path, dpi=120)
        if not keep_open:
            plt.close(self.fig)


class LiveControlPlot:
    """2 paineis (Bloco D): entrada u(t) (todos os canais) e y1(t) em malha
    fechada, com o setpoint plotado como serie de dados (mantem os valores
    anteriores em cada instante, nao so o atual -- ver add_sample). Slider
    opcional (modo "scrollbar do mouse") embutido na mesma figura -- arrastar
    o slider atualiza o setpoint em tempo real. Cada painel tem uma label no
    canto mostrando o valor atual.

    Numero de paineis fica FIXO em 2 (ou 3 com slider) independente de m
    (numero de entradas) -- so a quantidade de LINHAS dentro do painel de u
    cresce com m, o que e barato (set_data). O custo caro de redraw()
    (relayout do matplotlib) escala com o numero de PAINEIS, nao de canais
    -- por isso nao ha aqui paineis extras opcionais que multiplicariam
    esse custo (ver historico: uma versao anterior tinha ate 6 paineis e
    isso chegou a travar o laco de controle real, nao so o grafico).

    Os buffers usam uma janela deslizante de CONTROL_PLOT_WINDOW_SIZE
    amostras: o grafico mostra so as ultimas N e vai deslizando: o CSV salvo
    ao final do teste usa o log completo devolvido por plant.run_control,
    nao estes buffers."""

    def __init__(
        self,
        plant_name: str,
        m: int,
        setpoint_initial: float,
        # throttle frouxo (nao a cada amostra) para nao competir com o laco
        # de leitura da serial -- se redraw() atrasar a leitura, o buffer de
        # saida do Arduino enche e o Serial.print() do firmware trava
        # esperando espaco, congelando o CONTROLE real, nao so o grafico.
        # add_sample sempre grava no buffer independente do redraw, entao
        # nenhum dado se perde por causa desse throttle.
        refresh_interval_s: float = 0.3,
        with_slider: bool = False,
        slider_range: tuple[float, float] = (0.0, 100.0),
        window_size: int = CONTROL_PLOT_WINDOW_SIZE,
    ):
        self.m = m
        self.refresh_interval_s = refresh_interval_s
        self._last_refresh = 0.0

        self.t_buf: deque[float] = deque(maxlen=window_size)
        self.y1_buf: deque[float] = deque(maxlen=window_size)
        self.u_buf: list[deque[float]] = [deque(maxlen=window_size) for _ in range(m)]
        self.setpoint_buf: deque[float] = deque(maxlen=window_size)
        self._current_setpoint = setpoint_initial

        self._slider_dirty = False
        self._slider_value = setpoint_initial

        plt.ion()
        if with_slider:
            self.fig, (self.ax_u, self.ax_y, self.ax_slider) = plt.subplots(
                3, 1, figsize=(9, 8), gridspec_kw={"height_ratios": [3, 3, 1]},
                constrained_layout=True,
            )
            self.slider = Slider(
                self.ax_slider, "Setpoint", slider_range[0], slider_range[1],
                valinit=setpoint_initial,
            )
            self.slider.on_changed(self._on_slider_changed)
        else:
            self.fig, (self.ax_u, self.ax_y) = plt.subplots(
                2, 1, figsize=(9, 7), constrained_layout=True
            )
            self.slider = None

        self.fig.suptitle(f"Controle ao vivo -- {plant_name}")

        self.u_lines = [self.ax_u.plot([], [], label=f"u{j + 1}")[0] for j in range(m)]
        self.ax_u.set_title("Entrada u(t)")
        self.ax_u.set_xlabel("tempo [s]")
        self.ax_u.legend(loc="upper right")
        self.ax_u.grid(alpha=0.3)
        self.u_label = self._make_value_label(self.ax_u)

        (self.y1_line,) = self.ax_y.plot([], [], color="tab:blue", label="y1")
        (self.setpoint_line,) = self.ax_y.plot(
            [], [], color="k", lw=0.8, ls="--", label="setpoint"
        )
        self.ax_y.set_title("Malha fechada: y1(t)")
        self.ax_y.set_xlabel("tempo [s]")
        self.ax_y.legend(loc="upper right")
        self.ax_y.grid(alpha=0.3)
        self.y_label = self._make_value_label(self.ax_y)

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    @staticmethod
    def _make_value_label(ax):
        # canto superior ESQUERDO -- as legendas dos paineis usam
        # loc="upper right", entao a label de valor no canto oposto evita
        # sobrepor o texto da legenda
        return ax.text(
            0.02, 0.95, "", transform=ax.transAxes, ha="left", va="top", fontsize=9,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
        )

    def _on_slider_changed(self, value: float) -> None:
        self._slider_value = value
        self._slider_dirty = True

    def take_slider_change(self) -> float | None:
        """Retorna o novo valor do slider desde a ultima checagem, ou None
        se nao mudou."""
        if self._slider_dirty:
            self._slider_dirty = False
            return self._slider_value
        return None

    def add_sample(self, t_s: float, y1_val: float, u_vals, setpoint_val: float | None = None) -> None:
        if setpoint_val is not None:
            self._current_setpoint = setpoint_val
        self.t_buf.append(t_s)
        self.y1_buf.append(float(y1_val))
        for j in range(self.m):
            self.u_buf[j].append(float(u_vals[j]))
        # sempre grava o setpoint vigente (mesmo quando nao mudou nesta
        # amostra) -- assim a linha pontilhada vira uma serie real (funcao
        # em degrau) que preserva os valores anteriores em cada instante,
        # em vez de uma linha horizontal que salta inteira para o novo nivel
        self.setpoint_buf.append(self._current_setpoint)

        now = time.monotonic()
        if now - self._last_refresh < self.refresh_interval_s:
            return
        self._last_refresh = now
        self.redraw()

    def redraw(self) -> None:
        for j, line in enumerate(self.u_lines):
            line.set_data(self.t_buf, self.u_buf[j])
        self.ax_u.relim()
        self.ax_u.autoscale_view()
        if self.u_buf and self.u_buf[0]:
            self.u_label.set_text(
                ", ".join(f"u{j + 1}={self.u_buf[j][-1]:.3f}" for j in range(self.m))
            )

        self.y1_line.set_data(self.t_buf, self.y1_buf)
        self.setpoint_line.set_data(self.t_buf, self.setpoint_buf)
        self.ax_y.relim()
        self.ax_y.autoscale_view()
        if self.y1_buf:
            self.y_label.set_text(f"y1={self.y1_buf[-1]:.3f} | setpoint={self.setpoint_buf[-1]:.3f}")

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self, keep_open: bool = False, save_path: str | None = None) -> None:
        self.redraw()
        if save_path:
            self.fig.savefig(save_path, dpi=120)
        if not keep_open:
            plt.close(self.fig)
