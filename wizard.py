# -*- coding: utf-8 -*-
"""Assistente interativo de inicio (Bloco A): Simulacao vs Dados reais,
escolha/definicao de planta, porta COM. Produz uma WizardSession que
runner.py usa para seguir com o fluxo (aquisicao -> LMI -> controle).

Nao muda nada em config/, datadriven/ ou plants/ -- so orquestra a escolha
interativa do que ja existe (ou, no caso de "nova planta", instancia
plants.GenericPlant sobre firmware/boards/generic).
"""

import glob
import importlib
import os
from dataclasses import dataclass

import numpy as np
import serial.tools.list_ports

from config.base import ExperimentConfig
from plants.generic import M_MAX, N_MAX, GenericPlant
from plants.base import Plant

# valores padrao para parametros que o wizard NAO pergunta (fora do escopo
# pedido), usados apenas no fluxo de "nova planta"
DEFAULT_UBAR_PERCENT = 50.0
DEFAULT_RHO = 0.9
DEFAULT_SEED = 0
DEFAULT_SETTLE_DURATION_S = 2.0


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


# ---------------------------------------------------------------------------
# descoberta de configs existentes (config/*.py)
# ---------------------------------------------------------------------------

def _discover_configs(exclude_simulated: bool) -> dict[str, str]:
    """Retorna {nome_da_planta: dotted_module_path} para os arquivos em
    config/, exceto base.py e __init__.py. exclude_simulated filtra os
    modulos cujo nome de arquivo comeca com 'simulated'."""
    configs = {}
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    for path in sorted(glob.glob(os.path.join(config_dir, "*.py"))):
        module_name = os.path.splitext(os.path.basename(path))[0]
        if module_name in ("base", "__init__"):
            continue
        if exclude_simulated and module_name.startswith("simulated"):
            continue
        if not exclude_simulated and not module_name.startswith("simulated"):
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

    mode = prompt_choice("Como deseja rodar?", ["Simulacao", "Dados reais"])
    if mode == 0:
        return _wizard_simulation()
    return _wizard_real_data()


def _wizard_simulation() -> WizardSession:
    configs = _discover_configs(exclude_simulated=False)
    if not configs:
        raise RuntimeError("Nenhuma config simulada encontrada em config/ (esperado ex.: simulated_2x2.py).")
    names = list(configs.keys())
    chosen = names[prompt_choice("Planta simulada:", names)]
    module = importlib.import_module(configs[chosen])
    cfg: ExperimentConfig = module.CONFIG

    dt, T, excitation_amplitude, max_expected_state_deviation = _prompt_free_params_override(cfg)

    plant = cfg.make_plant()
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
    )


def _wizard_real_data() -> WizardSession:
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
    configs = _discover_configs(exclude_simulated=True)
    if not configs:
        raise RuntimeError("Nenhuma config real encontrada em config/.")
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

    port = choose_com_port()
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
    )
