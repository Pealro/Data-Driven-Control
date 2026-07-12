# -*- coding: utf-8 -*-
"""Thread de fundo pra ler o terminal sem bloquear o loop de controle ao
vivo. Um unico consumidor de stdin, usado pelos 3 modos do Bloco D: a
linha 'e' pede pra abortar (sempre, em qualquer modo); se
accept_setpoint_input=True, qualquer outra linha numerica vira um novo
setpoint (modo "setpoint via terminal")."""

import threading


class TerminalController:
    def __init__(self, n: int, accept_setpoint_input: bool = True):
        self.n = n
        self.accept_setpoint_input = accept_setpoint_input
        self._abort = threading.Event()
        self._lock = threading.Lock()
        self._pending_setpoint: list[float] | None = None
        self._thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _read_loop(self) -> None:
        while not self._abort.is_set():
            try:
                line = input()
            except EOFError:
                break
            line = line.strip()
            if line.lower() == "e":
                self._abort.set()
                break
            if self.accept_setpoint_input and line:
                values = self._parse_setpoint(line)
                if values is not None:
                    with self._lock:
                        self._pending_setpoint = values

    def _parse_setpoint(self, line: str) -> list[float] | None:
        try:
            parts = [float(v) for v in line.replace(",", " ").split()]
        except ValueError:
            print(f"    (setpoint invalido: '{line}' -- use numero(s) separados por espaco)")
            return None
        if len(parts) != self.n:
            print(f"    (esperado {self.n} valor(es) de setpoint, recebi {len(parts)})")
            return None
        return parts

    def should_abort(self) -> bool:
        return self._abort.is_set()

    def take_pending_setpoint(self) -> list[float] | None:
        with self._lock:
            value = self._pending_setpoint
            self._pending_setpoint = None
        return value

    def request_abort(self) -> None:
        self._abort.set()
