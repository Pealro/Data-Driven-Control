# -*- coding: utf-8 -*-
"""Assistente interativo de inicio (Bloco A): escolha/definicao de planta,
limites de entrada/saida, porta COM. Produz uma WizardSession que
runner.py usa para seguir com o fluxo (aquisicao -> LMI -> controle).

Nao muda nada em config/, datadriven/ ou plants/ -- so orquestra a escolha
interativa do que ja existe (ou, no caso de "nova planta", grava
firmware/boards/generic na placa e instancia plants.GenericPlant).
"""

import glob
import importlib
import os
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np
import serial.tools.list_ports

from config.base import ExperimentConfig
from plants.base import Plant
from plants.generic import M_MAX, N_MAX, GenericPlant

# valores padrao para parametros que o wizard NAO pergunta (fora do escopo
# pedido), usados apenas no fluxo de "nova planta"
DEFAULT_UBAR_PERCENT = 50.0
DEFAULT_RHO = 0.9
DEFAULT_SEED = 0
DEFAULT_SETTLE_DURATION_S = 2.0

_PROJECT_ROOT = os.path.dirname(__file__)


@dataclass
class WizardSession:
    plant_name: str
    plant: Plant
    T: int
    dt: float
    ubar: np.ndarray
    settle_duration_s: float
    excitation_amplitude: float
    max_expected_state_deviation: float
    rho: float
    seed: int | None
    # calibracao fisica opcional (ver calibration.py) -- None = sem
    # conversao, dados ficam em unidade crua (volts / % de duty)
    y_physical_min: float | None = None  # valor fisico quando o ADC le 0V
    y_physical_max: float | None = None  # valor fisico quando o ADC le 5V
    u_physical_min: float | None = None  # valor fisico quando o atuador esta em 0%
    u_physical_max: float | None = None  # valor fisico quando o atuador esta em 100%


# ---------------------------------------------------------------------------
# helpers de prompt
# ---------------------------------------------------------------------------

def prompt_choice(question: str, options: list[str]) -> int:
    """Mostra um menu numerado e retorna o INDICE escolhido (0-based)."""
    print(f"\n{question}")
    for i, option in enumerate(options):
        print(f"  {i + 1}) {option}")
    while True:
        raw = input(f"Escolha [1-{len(options)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"    Digite um numero entre 1 e {len(options)}.")


def prompt_float(question: str, default: float | None = None, min_value: float | None = None) -> float:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{question}{suffix}: ").strip()
        if raw == "" and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("    Digite um numero valido.")
            continue
        if min_value is not None and value < min_value:
            print(f"    Valor deve ser >= {min_value}.")
            continue
        return value


def prompt_int(
    question: str,
    default: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{question}{suffix}: ").strip()
        if raw == "" and default is not None:
            return default
        if not raw.lstrip("-").isdigit():
            print("    Digite um numero inteiro valido.")
            continue
        value = int(raw)
        if min_value is not None and value < min_value:
            print(f"    Valor deve ser >= {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"    Valor deve ser <= {max_value}.")
            continue
        return value


def prompt_float_or_unknown(question: str, default: float | None = None) -> float | None:
    """Digite 'd' para 'desconhecido' (retorna None -- diagnosticos e
    saturacao desativam a checagem correspondente). Enter em branco mantem
    o default (que tambem pode ser None)."""
    hint = f"Enter={default}" if default is not None else "Enter=d"
    while True:
        raw = input(f"{question} [d=desconhecido, {hint}]: ").strip().lower()
        if raw == "":
            return default
        if raw == "d":
            return None
        try:
            return float(raw)
        except ValueError:
            print("    Digite um numero, 'd' (desconhecido), ou Enter.")


def choose_com_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return input("\nNenhuma porta COM detectada. Digite a porta manualmente: ").strip()
    print("\nPortas COM conectadas:")
    for i, port in enumerate(ports):
        print(f"  {i + 1}) {port.device} -- {port.description}")
    print(f"  {len(ports) + 1}) Digitar manualmente")
    index = prompt_int("Escolha a porta", min_value=1, max_value=len(ports) + 1)
    if index == len(ports) + 1:
        return input("Porta: ").strip()
    return ports[index - 1].device


def _prompt_calibration(
    y_physical_min_default=None,
    y_physical_max_default=None,
    u_physical_min_default=None,
    u_physical_max_default=None,
):
    """Calibracao fisica (Bloco A): os valores extremos da planta em relacao
    a porta do Arduino. 'entrada' = leitura do sensor (porta analogica,
    0-5V); 'saida' = comando do atuador (PWM, 0-100%). 'd' = desconhecido
    desativa a conversao correspondente (dados ficam em unidade crua)."""
    print(
        "\nCalibracao fisica (digite 'd' se nao souber -- desativa a conversao"
        " correspondente, dados ficam em unidade crua):"
    )
    print("  Entrada = leitura do sensor na porta analogica do Arduino (0-5V):")
    y_physical_min = prompt_float_or_unknown(
        "    Valor minimo de entrada (valor fisico quando a porta analogica le 0V)",
        default=y_physical_min_default,
    )
    y_physical_max = prompt_float_or_unknown(
        "    Valor maximo de entrada (valor fisico quando a porta analogica le 5V)",
        default=y_physical_max_default,
    )
    print("  Saida = comando do atuador (PWM, 0-100%):")
    u_physical_min = prompt_float_or_unknown(
        "    Valor minimo de saida (valor fisico quando o atuador esta em 0%)",
        default=u_physical_min_default,
    )
    u_physical_max = prompt_float_or_unknown(
        "    Valor maximo de saida (valor fisico quando o atuador esta em 100%)",
        default=u_physical_max_default,
    )
    return y_physical_min, y_physical_max, u_physical_min, u_physical_max


# ---------------------------------------------------------------------------
# gravacao automatica do firmware generico (Bloco A: "nova planta")
# ---------------------------------------------------------------------------

def _find_pio_executable() -> str | None:
    found = shutil.which("pio")
    if found:
        return found
    candidates = [
        os.path.expanduser(r"~\.platformio\penv\Scripts\pio.exe"),
        os.path.expanduser("~/.platformio/penv/bin/pio"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def flash_generic_firmware(port: str) -> bool:
    """Compila e grava firmware/boards/generic na porta escolhida. Sempre
    grava de novo (idempotente, ~5-10s) -- evita o usuario ter que lembrar
    se ja gravou antes, e e a causa mais comum de a placa recusar um CFG
    com n/m maior que o firmware atualmente gravado suporta (ERR,NM_INVALIDO)."""
    pio = _find_pio_executable()
    if pio is None:
        print(
            "\nAVISO: PlatformIO (pio) nao encontrado neste computador -- nao consigo gravar"
            " firmware/boards/generic automaticamente. Grave manualmente antes de continuar"
            " (pio run -t upload --upload-port "
            f"{port} nesta pasta: firmware/boards/generic) ou o experimento vai falhar se a"
            " placa nao tiver esse firmware."
        )
        return not _confirm_local("Prosseguir mesmo assim?")

    board_dir = os.path.join(_PROJECT_ROOT, "firmware", "boards", "generic")
    print(f"\nGravando firmware/boards/generic na porta {port} (alguns segundos)...")
    result = subprocess.run(
        [pio, "run", "-d", board_dir, "-t", "upload", "--upload-port", port],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("    ERRO ao gravar o firmware generico:")
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        return False
    print("    Firmware gravado com sucesso.")
    return True


def _confirm_local(question: str) -> bool:
    raw = input(f"{question} [s/N]: ").strip().lower()
    return raw in ("s", "sim", "y", "yes")


# ---------------------------------------------------------------------------
# descoberta de configs existentes (config/*.py)
# ---------------------------------------------------------------------------

def _discover_configs() -> dict[str, str]:
    """Retorna {nome_da_planta: dotted_module_path} para os arquivos em
    config/, exceto base.py e __init__.py."""
    configs = {}
    config_dir = os.path.join(_PROJECT_ROOT, "config")
    for path in sorted(glob.glob(os.path.join(config_dir, "*.py"))):
        module_name = os.path.splitext(os.path.basename(path))[0]
        if module_name in ("base", "__init__"):
            continue
        dotted_path = f"config.{module_name}"
        module = importlib.import_module(dotted_path)
        configs[module.CONFIG.name] = dotted_path
    return configs


# ---------------------------------------------------------------------------
# fluxo principal
# ---------------------------------------------------------------------------

def run_wizard() -> WizardSession:
    print("=" * 70)
    print(" Controle data-driven -- assistente de inicio")
    print("=" * 70)

    sub_mode = prompt_choice(
        "Planta:", ["Planta ja estabelecida (config existente)", "Nova planta (definida agora)"]
    )
    if sub_mode == 0:
        return _wizard_established_plant()
    return _wizard_new_plant()


def _prompt_free_params_override(cfg: ExperimentConfig):
    print(f"\nParametros livres (Enter mantem o valor atual da config '{cfg.name}'):")
    dt = prompt_float("  Taxa de amostragem (dt) [s]", default=cfg.dt)
    T = prompt_int("  Numero de coletas (T)", default=cfg.T, min_value=1)
    excitation_amplitude = prompt_float(
        "  Amplitude de entrada (excitation_amplitude)", default=cfg.excitation_amplitude
    )
    max_expected_state_deviation = prompt_float(
        "  Amplitude de estado esperada (max_expected_state_deviation)",
        default=cfg.max_expected_state_deviation,
    )
    return dt, T, excitation_amplitude, max_expected_state_deviation


def _wizard_established_plant() -> WizardSession:
    configs = _discover_configs()
    if not configs:
        raise RuntimeError("Nenhuma config encontrada em config/.")
    names = list(configs.keys())
    chosen = names[prompt_choice("Planta ja estabelecida:", names)]
    dotted_path = configs[chosen]
    module = importlib.import_module(dotted_path)
    cfg: ExperimentConfig = module.CONFIG

    dt, T, excitation_amplitude, max_expected_state_deviation = _prompt_free_params_override(cfg)

    port = choose_com_port()
    if hasattr(module, "PORT"):
        module.PORT = port  # a lambda de make_plant le PORT do modulo em tempo de chamada
    plant = cfg.make_plant()

    y_physical_min, y_physical_max, u_physical_min, u_physical_max = _prompt_calibration()

    return WizardSession(
        plant_name=cfg.name,
        plant=plant,
        T=T,
        dt=dt,
        ubar=cfg.ubar,
        settle_duration_s=cfg.settle_duration_s,
        excitation_amplitude=excitation_amplitude,
        max_expected_state_deviation=max_expected_state_deviation,
        rho=cfg.rho,
        seed=cfg.seed,
        y_physical_min=y_physical_min,
        y_physical_max=y_physical_max,
        u_physical_min=u_physical_min,
        u_physical_max=u_physical_max,
    )


def _wizard_new_plant() -> WizardSession:
    plant_name = input("\nNome da planta: ").strip() or "planta_nova"

    print(f"\nParametros de entrada (firmware generico: ate {N_MAX} estados, ate {M_MAX} entradas):")
    n = prompt_int(f"  Numero de estados (1-{N_MAX})", min_value=1, max_value=N_MAX)
    m = prompt_int(f"  Numero de entradas (1-{M_MAX})", min_value=1, max_value=M_MAX)
    dt = prompt_float("  Taxa de amostragem (dt) [s]", min_value=0.0)

    T_min = (m + 1) * n + m  # condicao necessaria de persistencia de excitacao (De Persis & Tesi, 2020)
    print(f"    (minimo para persistencia de excitacao: T >= (m+1)n+m = {T_min})")
    T = prompt_int("  Numero de coletas (T)", default=T_min, min_value=T_min)

    excitation_amplitude = prompt_float("  Amplitude de entrada (excitation_amplitude)", min_value=0.0)
    max_expected_state_deviation = prompt_float(
        "  Amplitude de estado esperada (max_expected_state_deviation)", min_value=0.0
    )

    y_physical_min, y_physical_max, u_physical_min, u_physical_max = _prompt_calibration()

    port = choose_com_port()
    if not flash_generic_firmware(port):
        raise RuntimeError(
            "Firmware generico nao gravado -- corrija e tente novamente antes de conectar."
        )
    plant = GenericPlant(n=n, m=m, port=port, verbose=True)

    ubar = np.full(m, DEFAULT_UBAR_PERCENT)
    print(
        f"\n    (nao pedidos no wizard, usando padrao: ubar={ubar.tolist()}, "
        f"settle_duration_s={DEFAULT_SETTLE_DURATION_S}, rho={DEFAULT_RHO}, seed={DEFAULT_SEED})"
    )

    return WizardSession(
        plant_name=plant_name,
        plant=plant,
        T=T,
        dt=dt,
        ubar=ubar,
        settle_duration_s=DEFAULT_SETTLE_DURATION_S,
        excitation_amplitude=excitation_amplitude,
        max_expected_state_deviation=max_expected_state_deviation,
        rho=DEFAULT_RHO,
        seed=DEFAULT_SEED,
        y_physical_min=y_physical_min,
        y_physical_max=y_physical_max,
        u_physical_min=u_physical_min,
        u_physical_max=u_physical_max,
    )
