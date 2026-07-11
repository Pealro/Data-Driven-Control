# -*- coding: utf-8 -*-
"""Transporte serial ASCII vetorial, compartilhado por todas as plantas que
rodam o firmware DataDrivenProtocol (firmware/lib/DataDrivenProtocol).

Protocolo (115200 baud, linhas ASCII terminadas em '\\n'):

  PC -> Arduino:
    CFG,<T>,<dt_ms>,<n>,<m>,<ubar_1..ubar_m>,<settle_s>
    U,<k>,<du_1..du_m>
    GO
    K,<K_11..K_1n,K_21..K_mn>,<Tsp_1..Tsp_n>,<ctrl_s>   (K linha-major, m x n)
    X                                                     aborta a qualquer momento

  Arduino -> PC:
    ACK,CFG | ACK,U,<k> | ACK,GO | ACK,K
    S,<t_s>,<y_1..y_n>            streaming do assentamento (1 Hz)
    EQ,<ybar_1..ybar_n>           equilibrio medido
    D,<k>,<y_1..y_n>,<u_1..u_m>   amostra do experimento (u = nan,..,nan no ultimo k)
    WAITK                         dados enviados, aguardando K
    C,<t_s>,<y_1..y_n>,<u_1..u_m> streaming do controle em tempo real
    END | ERR,<msg>
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
        t_start = time.time()
        while True:
            line = self.read_line()
            if line == "":
                if timeout_s is not None and time.time() - t_start > timeout_s:
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
    """Implementa o protocolo vetorial CFG/U/GO/K/X <-> ACK/S/EQ/D/WAITK/C/END/ERR."""

    def __init__(self, link: SerialLink, n: int, m: int):
        self.link = link
        self.n = n
        self.m = m

    def send_config(self, T: int, dt_s: float, ubar: np.ndarray, settle_s: float) -> None:
        self.link.send(
            f"CFG,{T},{int(dt_s * 1000)},{self.n},{self.m},{fmt_vec(ubar, 3)},{int(settle_s)}"
        )
        self.link.wait_for("ACK,CFG", timeout_s=10)

    def send_excitation(self, du: np.ndarray, echo: bool = True) -> None:
        T = du.shape[1]
        for k in range(T):
            self.link.send(f"U,{k},{fmt_vec(du[:, k])}")
            self.link.wait_for(f"ACK,U,{k}", timeout_s=5)
        if echo:
            print(f"    Vetor de entrada ({T} amostras) enviado e confirmado.")

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
                vals = line.split(",")[1:]
                return np.array([float(v) for v in vals])
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

    def collect_experiment(self, T: int, on_sample=None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
                    on_sample(k, y_vals, u_vals)
            elif line.startswith("WAITK"):
                return t_raw, y_raw, u_raw
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

    def send_gain_and_stream(
        self, K: np.ndarray, setpoint: np.ndarray, duration_s: float, on_sample=None
    ) -> tuple[list[float], np.ndarray, np.ndarray]:
        n, m = self.n, self.m
        k_flat = K.reshape(m, n).flatten(order="C")
        self.link.send(f"K,{fmt_vec(k_flat, 6)},{fmt_vec(setpoint, 3)},{int(duration_s)}")
        self.link.wait_for("ACK,K", timeout_s=5)

        t_log: list[float] = []
        y_log: list[list[float]] = []
        u_log: list[list[float]] = []
        while True:
            line = self.link.read_line()
            if line == "":
                continue
            if line.startswith("C,"):
                parts = line.split(",")
                t_s = float(parts[1])
                y_vals = [float(v) for v in parts[2:2 + n]]
                u_vals = [float(v) for v in parts[2 + n:2 + n + m]]
                t_log.append(t_s)
                y_log.append(y_vals)
                u_log.append(u_vals)
                if on_sample:
                    on_sample(t_s, y_vals, u_vals)
            elif line.startswith("END"):
                break
            elif line.startswith("ERR"):
                raise RuntimeError(f"Arduino reportou erro: {line}")

        y_arr = np.array(y_log).T if y_log else np.zeros((n, 0))
        u_arr = np.array(u_log).T if u_log else np.zeros((m, 0))
        return t_log, y_arr, u_arr

    def abort(self) -> None:
        self.link.send("X")
