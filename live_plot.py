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
        refresh_interval_s: float = 0.2,
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
        all_u = [value for channel in self.u_buf for value in channel]
        if all_u:
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
    """Paineis (Bloco D), sempre presentes: entrada u(t) (todos os canais) e
    y1(t) em malha fechada, com o setpoint plotado como serie de dados
    (mantem os valores anteriores em cada instante, nao so o atual -- ver
    add_sample). Dois pares de paineis opcionais, cada um cobrindo controle
    E erro:
      show_instantaneous_power -- potencia instantanea, ||u(k)||^2/||e(k)||^2
        por amostra (nao acumula);
      show_total_energy -- energia total, soma corrida de ||u(k)||^2/||e(k)||^2
        desde o inicio do teste (energia no sentido formal de sinal).
    e = y - setpoint em TODOS os n estados medidos (nao so y1). Cada painel
    tem uma label no canto mostrando o valor atual (instantaneo). Slider
    opcional (modo "scrollbar do mouse") embutido na mesma figura.

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
        show_instantaneous_power: bool = False,
        show_total_energy: bool = False,
    ):
        self.m = m
        self.refresh_interval_s = refresh_interval_s
        self._last_refresh = 0.0
        self.show_instantaneous_power = show_instantaneous_power
        self.show_total_energy = show_total_energy

        self.t_buf: deque[float] = deque(maxlen=window_size)
        self.y1_buf: deque[float] = deque(maxlen=window_size)
        self.u_buf: list[deque[float]] = [deque(maxlen=window_size) for _ in range(m)]
        self.setpoint_buf: deque[float] = deque(maxlen=window_size)
        self.control_power_buf: deque[float] = deque(maxlen=window_size)
        self.error_power_buf: deque[float] = deque(maxlen=window_size)
        self.control_energy_buf: deque[float] = deque(maxlen=window_size)
        self.error_energy_buf: deque[float] = deque(maxlen=window_size)
        self._current_setpoint = setpoint_initial
        self._control_energy_total = 0.0
        self._error_energy_total = 0.0

        self._slider_dirty = False
        self._slider_value = setpoint_initial

        # grade de 2 colunas (u|y na primeira linha, potencia/energia
        # controle|erro nas linhas seguintes, slider ocupando a linha
        # inteira por baixo) -- evita uma coluna unica muito alta quando
        # varios paineis opcionais estao ativos, e constrained_layout=True
        # recalcula o espacamento a cada redraw (tight_layout() so calcula
        # uma vez, na criacao, e desalinha conforme os dados/legendas mudam)
        n_rows = 1 + int(show_instantaneous_power) + int(show_total_energy)
        height_ratios = [3] + [2] * (n_rows - 1)
        if with_slider:
            height_ratios.append(1)

        plt.ion()
        self.fig = plt.figure(
            figsize=(12, 3.4 * n_rows + (1.2 if with_slider else 0)), constrained_layout=True
        )
        grid = self.fig.add_gridspec(
            n_rows + int(with_slider), 2, height_ratios=height_ratios
        )
        self.ax_u = self.fig.add_subplot(grid[0, 0])
        self.ax_y = self.fig.add_subplot(grid[0, 1])
        row = 1
        if show_instantaneous_power:
            self.ax_control_power = self.fig.add_subplot(grid[row, 0])
            self.ax_error_power = self.fig.add_subplot(grid[row, 1])
            row += 1
        if show_total_energy:
            self.ax_control_energy = self.fig.add_subplot(grid[row, 0])
            self.ax_error_energy = self.fig.add_subplot(grid[row, 1])
            row += 1
        if with_slider:
            self.ax_slider = self.fig.add_subplot(grid[row, :])
            self.slider = Slider(
                self.ax_slider, "Setpoint", slider_range[0], slider_range[1],
                valinit=setpoint_initial,
            )
            self.slider.on_changed(self._on_slider_changed)
        else:
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

        if show_instantaneous_power:
            (self.control_power_line,) = self.ax_control_power.plot([], [], color="tab:orange")
            self.ax_control_power.set_title("Potencia instantanea de controle -- ||u(k)||^2")
            self.ax_control_power.set_xlabel("tempo [s]")
            self.ax_control_power.grid(alpha=0.3)
            self.control_power_label = self._make_value_label(self.ax_control_power)

            (self.error_power_line,) = self.ax_error_power.plot([], [], color="tab:red")
            self.ax_error_power.set_title("Potencia instantanea do erro -- ||e(k)||^2")
            self.ax_error_power.set_xlabel("tempo [s]")
            self.ax_error_power.grid(alpha=0.3)
            self.error_power_label = self._make_value_label(self.ax_error_power)

        if show_total_energy:
            (self.control_energy_line,) = self.ax_control_energy.plot([], [], color="tab:orange")
            self.ax_control_energy.set_title("Energia total de controle -- soma ||u(k)||^2")
            self.ax_control_energy.set_xlabel("tempo [s]")
            self.ax_control_energy.grid(alpha=0.3)
            self.control_energy_label = self._make_value_label(self.ax_control_energy)

            (self.error_energy_line,) = self.ax_error_energy.plot([], [], color="tab:red")
            self.ax_error_energy.set_title("Energia total do erro -- soma ||e(k)||^2")
            self.ax_error_energy.set_xlabel("tempo [s]")
            self.ax_error_energy.grid(alpha=0.3)
            self.error_energy_label = self._make_value_label(self.ax_error_energy)

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

    def add_sample(
        self,
        t_s: float,
        y1_val: float,
        u_vals,
        setpoint_val: float | None = None,
        error_vals=None,
    ) -> None:
        """error_vals, se fornecido, e o vetor e = y - setpoint em TODOS os n
        estados medidos (nao so y1) -- usado para potencia/energia do erro;
        o restante do plot continua y1-only."""
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

        control_power = sum(float(v) ** 2 for v in u_vals)
        error_power = sum(float(v) ** 2 for v in error_vals) if error_vals is not None else 0.0
        self._control_energy_total += control_power
        self._error_energy_total += error_power
        if self.show_instantaneous_power:
            self.control_power_buf.append(control_power)
            self.error_power_buf.append(error_power)
        if self.show_total_energy:
            self.control_energy_buf.append(self._control_energy_total)
            self.error_energy_buf.append(self._error_energy_total)

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

        if self.show_instantaneous_power:
            self.control_power_line.set_data(self.t_buf, self.control_power_buf)
            self.ax_control_power.relim()
            self.ax_control_power.autoscale_view()
            if self.control_power_buf:
                self.control_power_label.set_text(f"{self.control_power_buf[-1]:.4f}")

            self.error_power_line.set_data(self.t_buf, self.error_power_buf)
            self.ax_error_power.relim()
            self.ax_error_power.autoscale_view()
            if self.error_power_buf:
                self.error_power_label.set_text(f"{self.error_power_buf[-1]:.4f}")

        if self.show_total_energy:
            self.control_energy_line.set_data(self.t_buf, self.control_energy_buf)
            self.ax_control_energy.relim()
            self.ax_control_energy.autoscale_view()
            if self.control_energy_buf:
                self.control_energy_label.set_text(f"{self.control_energy_buf[-1]:.4f}")

            self.error_energy_line.set_data(self.t_buf, self.error_energy_buf)
            self.ax_error_energy.relim()
            self.ax_error_energy.autoscale_view()
            if self.error_energy_buf:
                self.error_energy_label.set_text(f"{self.error_energy_buf[-1]:.4f}")

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

    def close(self, keep_open: bool = False, save_path: str | None = None) -> None:
        self.redraw()
        if save_path:
            self.fig.savefig(save_path, dpi=120)
        if not keep_open:
            plt.close(self.fig)
