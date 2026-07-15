# -*- coding: utf-8 -*-
"""Transporte serial ASCII vetorial, compartilhado por todas as plantas que
rodam o firmware DataDrivenProtocol (firmware/lib/DataDrivenProtocol).

Protocolo (115200 baud, linhas ASCII terminadas em '\\n'):

  PC -> Arduino:
    CFG,<T>,<dt_ms>,<n>,<m>,<ubar_1..ubar_m>,<settle_duration_s>,<excitation_amplitude>,<seed>
    GO
    K,<K_11..K_1n,K_21..K_mn>,<setpoint_1..setpoint_n>,<control_duration_s>   (K linha-major, m x n)
    X                                                     aborta a qualquer momento

  Arduino -> PC:
    ACK,CFG | ACK,GO | ACK,K
    S,<t_s>,<y_1..y_n>            streaming do assentamento (1 Hz)
    EQ,<ybar_1..ybar_n>           equilibrio medido
    D,<k>,<t_ms>,<y_1..y_n>,<u_1..u_m>   amostra do experimento (u = nan,..,nan no ultimo k)
    WAITK                         dados enviados, aguardando K
    C,<t_ms>,<y_1..y_n>,<u_1..u_m> streaming do controle em tempo real
    END | ERR,<msg>

A excitacao delta_u(k) nao e enviada pelo PC: o firmware a gera sob demanda
com um PRNG determinístico semeado por <seed> (ver firmware/lib/
DataDrivenProtocol/Xorshift32.h), entao nao ha buffer O(T) no Arduino e a
janela T deixa de ser limitada pela RAM do microcontrolador.
"""

import time

import numpy as np
import serial


def fmt_vec(values, prec: int = 4) -> str:
    return ",".join(f"{v:.{prec}f}" for v in values)


class SerialLink:
    """Transporte de linhas ASCII cru, sem conhecimento do protocolo."""

    def __init__(self, port: str, baud: int = 115200, timeout_s: float = 3.0):
        self.ser = serial.Serial(port, baud, timeout=timeout_s)
        time.sleep(2.5)  # o Uno reseta ao abrir a porta
        self.ser.reset_input_buffer()

    def send(self, line: str) -> None:
        self.ser.write((line + "\n").encode("ascii"))

    def read_line(self) -> str:
        return self.ser.readline().decode("ascii", errors="ignore").strip()

    def wait_for(self, prefix: str, echo: bool = False, timeout_s: float | None = None) -> str:
        """Le linhas ate encontrar uma que comece com `prefix`. Repassa ERR."""
        start_time = time.time()
        while True:
            line = self.read_line()
            if line == "":
                if timeout_s is not None and time.time() - start_time > timeout_s:
                    raise TimeoutError(f"timeout esperando '{prefix}'")
                continue
            if echo:
                print("   [arduino]", line)
            if line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")
            if line.startswith(prefix):
                return line

    def close(self) -> None:
        self.ser.close()


class DataDrivenSerialProtocol:
    """Implementa o protocolo vetorial CFG/GO/K/X <-> ACK/S/EQ/D/WAITK/C/END/ERR."""

    def __init__(self, link: SerialLink, n: int, m: int):
        self.link = link
        self.n = n
        self.m = m

    def send_config(
        self,
        T: int,
        dt_s: float,
        ubar: np.ndarray,
        settle_duration_s: float,
        excitation_amplitude: float,
        seed: int | None,
    ) -> None:
        seed_value = 0 if seed is None else int(seed)
        self.link.send(
            f"CFG,{T},{int(dt_s * 1000)},{self.n},{self.m},{fmt_vec(ubar, 3)},"
            f"{int(settle_duration_s)},{excitation_amplitude:.4f},{seed_value}"
        )
        self.link.wait_for("ACK,CFG", timeout_s=10)

    def go_and_settle(self, on_progress=None) -> np.ndarray:
        self.link.send("GO")
        self.link.wait_for("ACK,GO", timeout_s=5)
        while True:
            line = self.link.read_line()
            if line == "":
                continue
            if line.startswith("S,"):
                if on_progress:
                    on_progress(line)
            elif line.startswith("EQ,"):
                equilibrium_values = line.split(",")[1:]
                return np.array([float(v) for v in equilibrium_values])
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

    def collect_experiment(
        self, T: int, on_sample=None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Retorna (t_raw, y_raw, u_raw). t_raw (T+1,) e o tempo REAL (s,
        medido via millis() no Arduino) de cada amostra desde o inicio do
        experimento -- permite detectar se o dt configurado foi realmente
        alcancado ou se o laco ficou limitado pelo tempo de execucao."""
        n, m = self.n, self.m
        t_raw = np.zeros(T + 1)
        y_raw = np.zeros((n, T + 1))
        u_raw = np.zeros((m, T))
        while True:
            line = self.link.read_line()
            if line == "":
                continue
            if line.startswith("D,"):
                parts = line.split(",")
                k = int(parts[1])
                t_raw[k] = float(parts[2]) / 1000.0
                y_vals = parts[3:3 + n]
                u_vals = parts[3 + n:3 + n + m]
                y_raw[:, k] = [float(v) for v in y_vals]
                if u_vals and u_vals[0] != "nan":
                    u_raw[:, k] = [float(v) for v in u_vals]
                if on_sample:
                    on_sample(k, t_raw[k], y_vals, u_vals)
            elif line.startswith("WAITK"):
                return t_raw, y_raw, u_raw
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

    def send_gain_and_stream(
        self,
        K: np.ndarray,
        setpoint: np.ndarray,
        duration_s: float,
        on_sample=None,
        should_abort=None,
    ) -> tuple[list[float], np.ndarray, np.ndarray]:
        """Roda a malha fechada (firmware autonomo, dt exato via millis()).

        on_sample(t_s, y_vals, u_vals), se fornecido, e chamado a cada amostra
        e pode retornar um novo setpoint (lista/array de n valores) para
        atualizar a malha em tempo real (comando SP, sem reiniciar o timing
        nem o ganho K) -- ou None para manter o setpoint atual. Usado pelos
        modos de controle interativo (terminal, slider, funcao de entrada).

        should_abort(), se fornecido, e checado a cada amostra (e durante
        esperas sem dado); se retornar True, envia X e encerra o streaming.
        duration_s=0 roda indefinidamente ate should_abort ou Ctrl+C/abort().
        """
        n, m = self.n, self.m
        flattened_K = K.reshape(m, n).flatten(order="C")
        self.link.send(
            f"K,{fmt_vec(flattened_K, 6)},{fmt_vec(setpoint, 3)},{int(duration_s)}"
        )
        self.link.wait_for("ACK,K", timeout_s=5)

        t_log: list[float] = []
        y_log: list[list[float]] = []
        u_log: list[list[float]] = []
        while True:
            line = self.link.read_line()
            if line == "":
                if should_abort and should_abort():
                    self._abort_and_wait_end()
                    break
                continue
            if line.startswith("C,"):
                parts = line.split(",")
                t_s = float(parts[1]) / 1000.0  # firmware manda t_ms inteiro (ver DataDrivenProtocol.h)
                y_vals = [float(v) for v in parts[2:2 + n]]
                u_vals = [float(v) for v in parts[2 + n:2 + n + m]]
                t_log.append(t_s)
                y_log.append(y_vals)
                u_log.append(u_vals)
                if on_sample:
                    new_setpoint = on_sample(t_s, y_vals, u_vals)
                    if new_setpoint is not None:
                        self.link.send(f"SP,{fmt_vec(new_setpoint, 3)}")
                if should_abort and should_abort():
                    self._abort_and_wait_end()
                    break
            elif line.startswith("END"):
                break
            elif line.startswith("ACK,SP"):
                continue
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

        y_log_matrix = np.array(y_log).T if y_log else np.zeros((n, 0))
        u_log_matrix = np.array(u_log).T if u_log else np.zeros((m, 0))
        return t_log, y_log_matrix, u_log_matrix

    def send_external_control_and_stream(
        self,
        dt_s: float,
        duration_s: float,
        compute_u,
        on_sample=None,
        should_abort=None,
    ) -> tuple[list[float], np.ndarray, np.ndarray]:
        """Controle pautado pelo PC (firmware em EXTCONTROL): a cada passo o
        Arduino manda EC,<t_ms>,<y..>,<u_aplicado_anterior..>, o PC calcula
        u = compute_u(y) e responde URAW,<u..>. A lei (Koopman racional /
        delay-embedding) vive no compute_u, no PC.

        compute_u(y_vals) -> u (lista/array de m valores ou escalar). Levantar
        excecao dentro de compute_u (ex.: denominador racional singular) aborta
        o controle com seguranca (manda X). Retorna (t_log, y_log(n,N),
        u_log(m,N)) -- y_log[k] alinhado com o u aplicado que aparece no EC
        seguinte, mesma convencao de save_control_test_csv."""
        n, m = self.n, self.m
        self.link.send(f"XCTRL,{int(dt_s * 1000)},{int(duration_s)}")
        self.link.wait_for("ACK,XCTRL", timeout_s=5)

        t_log: list[float] = []
        y_log: list[list[float]] = []
        u_log: list[list[float]] = []
        while True:
            line = self.link.read_line()
            if line == "":
                if should_abort and should_abort():
                    self._abort_and_wait_end()
                    break
                continue
            if line.startswith("EC,"):
                parts = line.split(",")
                t_s = float(parts[1]) / 1000.0
                y_vals = [float(v) for v in parts[2:2 + n]]
                u_applied_prev = [float(v) for v in parts[2 + n:2 + n + m]]
                # loga (t, y(k), u_aplicado(k-1)) -- o EC carrega o u do passo
                # anterior ja saturado, alinhando y com o u que o produziu
                if t_log:  # o primeiro EC traz u_aplicado_prev = ubar (nao e um passo de controle)
                    u_log[-1] = u_applied_prev
                try:
                    u = compute_u(y_vals)
                except Exception:
                    self._abort_and_wait_end()
                    raise
                u_vec = np.atleast_1d(np.asarray(u, dtype=float)).reshape(m)
                self.link.send(f"URAW,{fmt_vec(u_vec, 4)}")
                t_log.append(t_s)
                y_log.append(y_vals)
                u_log.append([0.0] * m)  # placeholder; preenchido pelo proximo EC
                if on_sample:
                    on_sample(t_s, y_vals, u_vec.tolist())
                if should_abort and should_abort():
                    self._abort_and_wait_end()
                    break
            elif line.startswith("END"):
                break
            elif line.startswith("ACK,"):
                continue
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

        # descarta o ultimo passo (u ainda nao confirmado pelo EC seguinte) p/
        # manter t/y/u do mesmo comprimento e todos com u aplicado real
        if t_log:
            t_log, y_log, u_log = t_log[:-1], y_log[:-1], u_log[:-1]
        y_log_matrix = np.array(y_log).T if y_log else np.zeros((n, 0))
        u_log_matrix = np.array(u_log).T if u_log else np.zeros((m, 0))
        return t_log, y_log_matrix, u_log_matrix

    def _abort_and_wait_end(self) -> None:
        """Manda X e tenta confirmar o END do Arduino, mas NUNCA propaga
        excecao daqui: o pedido de abortar do usuario tem que ser respeitado
        mesmo se a confirmacao demorar/nao chegar (porta serial lenta,
        amostra em transito, etc.) -- travar o programa numa situacao dessas
        seria pior do que so encerrar sem a confirmacao."""
        try:
            self.link.send("X")
            self.link.wait_for("END", timeout_s=5)
        except (TimeoutError, RuntimeError):
            pass

    def abort(self) -> None:
        self.link.send("X")
