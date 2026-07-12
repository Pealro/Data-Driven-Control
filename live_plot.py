# -*- coding: utf-8 -*-
"""Plots ao vivo (Bloco B: aquisicao; Bloco D: controle). Atualiza em
throttle de tempo (nao a cada amostra) para nao comprometer o dt medido
durante a coleta -- o mesmo cuidado que ja tomamos com a precisao do
timestamp do firmware nesta sessao."""

import time

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider


class LiveAcquisitionPlot:
    """3 paineis: entrada u(t), saida y(t), distribuicao (histograma) de u
    coletado ate agora."""

    def __init__(self, plant_name: str, n: int, m: int, refresh_interval_s: float = 0.2):
        self.n = n
        self.m = m
        self.refresh_interval_s = refresh_interval_s
        self._last_refresh = 0.0

        self.t_buf: list[float] = []
        self.y_buf: list[list[float]] = [[] for _ in range(n)]
        self.u_buf: list[list[float]] = [[] for _ in range(m)]

        plt.ion()
        self.fig, (self.ax_u, self.ax_y, self.ax_hist) = plt.subplots(3, 1, figsize=(9, 9))
        self.fig.suptitle(f"Aquisicao ao vivo -- {plant_name}")

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

        self.fig.tight_layout()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def add_sample(self, t_s: float, y_vals, u_vals) -> None:
        self.t_buf.append(t_s)
        for i in range(self.n):
            self.y_buf[i].append(float(y_vals[i]))
        for j in range(self.m):
            self.u_buf[j].append(float(u_vals[j]))

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
        all_u = [value for channel in self.u_buf for value in channel]
        if all_u:
            self.ax_hist.hist(all_u, bins=20, color="tab:red", alpha=0.75)
        self.ax_hist.set_title("Distribuicao de u coletado")
        self.ax_hist.grid(alpha=0.3)

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
    fechada. Slider opcional (modo "scrollbar do mouse") embutido na mesma
    figura -- arrastar o slider atualiza o setpoint em tempo real."""

    def __init__(
        self,
        plant_name: str,
        m: int,
        setpoint_initial: float,
        refresh_interval_s: float = 0.15,
        with_slider: bool = False,
        slider_range: tuple[float, float] = (0.0, 100.0),
    ):
        self.m = m
        self.refresh_interval_s = refresh_interval_s
        self._last_refresh = 0.0

        self.t_buf: list[float] = []
        self.y1_buf: list[float] = []
        self.u_buf: list[list[float]] = [[] for _ in range(m)]

        self._slider_dirty = False
        self._slider_value = setpoint_initial

        plt.ion()
        if with_slider:
            self.fig, (self.ax_u, self.ax_y, self.ax_slider) = plt.subplots(
                3, 1, figsize=(9, 8), gridspec_kw={"height_ratios": [3, 3, 1]}
            )
            self.slider = Slider(
                self.ax_slider, "Setpoint", slider_range[0], slider_range[1],
                valinit=setpoint_initial,
            )
            self.slider.on_changed(self._on_slider_changed)
        else:
            self.fig, (self.ax_u, self.ax_y) = plt.subplots(2, 1, figsize=(9, 7))
            self.slider = None

        self.fig.suptitle(f"Controle ao vivo -- {plant_name}")

        self.u_lines = [self.ax_u.plot([], [], label=f"u{j + 1}")[0] for j in range(m)]
        self.ax_u.set_title("Entrada u(t)")
        self.ax_u.set_xlabel("tempo [s]")
        self.ax_u.legend(loc="upper right")
        self.ax_u.grid(alpha=0.3)

        (self.y1_line,) = self.ax_y.plot([], [], color="tab:blue", label="y1")
        self.setpoint_line = self.ax_y.axhline(
            setpoint_initial, color="k", lw=0.8, ls="--", label="setpoint"
        )
        self.ax_y.set_title("Malha fechada: y1(t)")
        self.ax_y.set_xlabel("tempo [s]")
        self.ax_y.legend(loc="upper right")
        self.ax_y.grid(alpha=0.3)

        self.fig.tight_layout()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

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
        self.t_buf.append(t_s)
        self.y1_buf.append(float(y1_val))
        for j in range(self.m):
            self.u_buf[j].append(float(u_vals[j]))
        if setpoint_val is not None:
            self.setpoint_line.set_ydata([setpoint_val, setpoint_val])

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

        self.y1_line.set_data(self.t_buf, self.y1_buf)
        self.ax_y.relim()
        self.ax_y.autoscale_view()

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self, keep_open: bool = False, save_path: str | None = None) -> None:
        self.redraw()
        if save_path:
            self.fig.savefig(save_path, dpi=120)
        if not keep_open:
            plt.close(self.fig)
