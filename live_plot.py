# -*- coding: utf-8 -*-
"""Plots ao vivo (Bloco B: aquisicao; Bloco D: controle). Atualiza em
throttle de tempo (nao a cada amostra) para nao comprometer o dt medido
durante a coleta -- o mesmo cuidado que ja tomamos com a precisao do
timestamp do firmware nesta sessao."""

import time
from collections import deque

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

CONTROL_PLOT_WINDOW_SIZE = 1000  # janela deslizante (Bloco D): mantem as ultimas
# 1000 amostras no grafico e desliza a partir dai -- o CSV salvo continua com
# o historico completo (t_log/y_log/u_log vem de plant.run_control, nao destes
# buffers de plot)

ACQUISITION_PLOT_WINDOW_SIZE = 1000  # janela deslizante (Bloco B), mesmo raciocinio
ACQUISITION_U_REDRAW_EVERY = 20  # painel de entrada (u) so redesenha a cada N
# amostras coletadas -- ele e o mais caro de atualizar (relim/autoscale a cada
# chamada) e dt pode ser bem menor que refresh_interval_s (ex.: rc_circuit
# dt=5ms), entao sem isso o laco de aquisicao trava tentando manter o plot em dia


class LiveAcquisitionPlot:
    """3 paineis: entrada u(t), saida y(t), distribuicao (histograma) de u
    coletado ate agora. O painel de u atualiza os dados a cada
    ACQUISITION_U_REDRAW_EVERY amostras (nao a cada redraw) -- ver add_sample."""

    def __init__(
        self,
        plant_name: str,
        n: int,
        m: int,
        refresh_interval_s: float = 0.2,
        window_size: int = ACQUISITION_PLOT_WINDOW_SIZE,
        u_redraw_every: int = ACQUISITION_U_REDRAW_EVERY,
    ):
        self.n = n
        self.m = m
        self.refresh_interval_s = refresh_interval_s
        self._last_refresh = 0.0
        self._u_redraw_every = u_redraw_every
        self._sample_count = 0

        self.t_buf: deque[float] = deque(maxlen=window_size)
        self.y_buf: list[deque[float]] = [deque(maxlen=window_size) for _ in range(n)]
        self.u_buf: list[deque[float]] = [deque(maxlen=window_size) for _ in range(m)]

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
        self._sample_count += 1

        now = time.monotonic()
        if now - self._last_refresh < self.refresh_interval_s:
            return
        self._last_refresh = now
        self.redraw()

    def redraw(self, force_u: bool = False) -> None:
        if force_u or self._sample_count % self._u_redraw_every == 0:
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
        self.redraw(force_u=True)  # garante que o estado final (todas as amostras) aparece
        if save_path:
            self.fig.savefig(save_path, dpi=120)
        if not keep_open:
            plt.close(self.fig)


class LiveControlPlot:
    """4 paineis (Bloco D): entrada u(t) (todos os canais), y1(t) em malha
    fechada (com o setpoint plotado como serie de dados -- mantem os valores
    anteriores em cada instante, nao so o atual, ver add_sample), energia de
    controle instantanea (||u(k)||^2, todos os canais de entrada) e energia
    do erro instantanea (||e(k)||^2, e = y - setpoint em todos os n estados
    medidos). Slider opcional (modo "scrollbar do mouse") embutido na mesma
    figura -- arrastar o slider atualiza o setpoint em tempo real.

    Os buffers usam uma janela deslizante de CONTROL_PLOT_WINDOW_SIZE
    amostras: o grafico mostra so as ultimas N e vai deslizando: o CSV salvo
    ao final do teste usa o log completo devolvido por plant.run_control,
    nao estes buffers."""

    def __init__(
        self,
        plant_name: str,
        m: int,
        setpoint_initial: float,
        refresh_interval_s: float = 0.15,
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
        self.control_energy_buf: deque[float] = deque(maxlen=window_size)
        self.error_energy_buf: deque[float] = deque(maxlen=window_size)
        self._current_setpoint = setpoint_initial

        self._slider_dirty = False
        self._slider_value = setpoint_initial

        plt.ion()
        if with_slider:
            self.fig, (
                self.ax_u, self.ax_y, self.ax_control_energy, self.ax_error_energy, self.ax_slider,
            ) = plt.subplots(
                5, 1, figsize=(9, 13), gridspec_kw={"height_ratios": [3, 3, 2, 2, 1]}
            )
            self.slider = Slider(
                self.ax_slider, "Setpoint", slider_range[0], slider_range[1],
                valinit=setpoint_initial,
            )
            self.slider.on_changed(self._on_slider_changed)
        else:
            self.fig, (
                self.ax_u, self.ax_y, self.ax_control_energy, self.ax_error_energy,
            ) = plt.subplots(4, 1, figsize=(9, 11))
            self.slider = None

        self.fig.suptitle(f"Controle ao vivo -- {plant_name}")

        self.u_lines = [self.ax_u.plot([], [], label=f"u{j + 1}")[0] for j in range(m)]
        self.ax_u.set_title("Entrada u(t)")
        self.ax_u.set_xlabel("tempo [s]")
        self.ax_u.legend(loc="upper right")
        self.ax_u.grid(alpha=0.3)

        (self.y1_line,) = self.ax_y.plot([], [], color="tab:blue", label="y1")
        (self.setpoint_line,) = self.ax_y.plot(
            [], [], color="k", lw=0.8, ls="--", label="setpoint"
        )
        self.ax_y.set_title("Malha fechada: y1(t)")
        self.ax_y.set_xlabel("tempo [s]")
        self.ax_y.legend(loc="upper right")
        self.ax_y.grid(alpha=0.3)

        (self.control_energy_line,) = self.ax_control_energy.plot([], [], color="tab:orange")
        self.ax_control_energy.set_title("Energia de controle instantanea ||u(k)||^2")
        self.ax_control_energy.set_xlabel("tempo [s]")
        self.ax_control_energy.grid(alpha=0.3)

        (self.error_energy_line,) = self.ax_error_energy.plot([], [], color="tab:red")
        self.ax_error_energy.set_title("Energia do erro instantanea ||e(k)||^2")
        self.ax_error_energy.set_xlabel("tempo [s]")
        self.ax_error_energy.grid(alpha=0.3)

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

    def add_sample(
        self,
        t_s: float,
        y1_val: float,
        u_vals,
        setpoint_val: float | None = None,
        error_vals=None,
    ) -> None:
        """error_vals, se fornecido, e o vetor e = y - setpoint em TODOS os n
        estados medidos (nao so y1) -- usado so para a energia do erro
        (ax_error_energy); o restante do plot continua y1-only."""
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
        self.control_energy_buf.append(sum(float(v) ** 2 for v in u_vals))
        self.error_energy_buf.append(
            sum(float(v) ** 2 for v in error_vals) if error_vals is not None else 0.0
        )

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
        self.setpoint_line.set_data(self.t_buf, self.setpoint_buf)
        self.ax_y.relim()
        self.ax_y.autoscale_view()

        self.control_energy_line.set_data(self.t_buf, self.control_energy_buf)
        self.ax_control_energy.relim()
        self.ax_control_energy.autoscale_view()

        self.error_energy_line.set_data(self.t_buf, self.error_energy_buf)
        self.ax_error_energy.relim()
        self.ax_error_energy.autoscale_view()

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self, keep_open: bool = False, save_path: str | None = None) -> None:
        self.redraw()
        if save_path:
            self.fig.savefig(save_path, dpi=120)
        if not keep_open:
            plt.close(self.fig)
