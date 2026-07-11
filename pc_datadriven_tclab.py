# -*- coding: utf-8 -*-
"""
===============================================================================
 pc_datadriven_tclab.py
 Controle data-driven no TCLab
 Lado PC -- planta SISO: Q1 (aquecedor 1) -> T1 (sensor 1), 
 numero estados = 1, numero inputs = 1

 Fluxo:
   1. Gera o vetor de excitacao du(k) ~ U(-AMP_ENTRADA, +AMP_ENTRADA)
   2. Envia configuracao + vetor ao Arduino (sketch tclab_datadriven.ino)
   3. Arduino assenta a planta em UBAR, mede o equilibrio Tbar e faz o
      experimento; o PC recebe as amostras via serial
   4. Monta X0, X1 (desvios de estado) e U0 (desvios de entrada APLICADOS,
      ja com saturacao 0..100%)
   5. Verifica persistencia de excitacao: rank([U0; X0]) == n + m
   6. Resolve a LMI data-driven com margem rho (eq. (15) generalizada):
         [ rho^2 (X0 Q)   X1 Q ]
         [ (X1 Q)'        X0 Q ]  > 0 ,   X0 Q > 0
         K = U0 Q (X0 Q)^-1        (so dados -- nenhum modelo identificado)
   7. Verificacao de estabilidade data-driven: |eig(X1 GK)| < rho < 1
   8. Envia K ao Arduino e recebe entrada/saida/controle em tempo real
   9. Salva CSVs e graficos

 Dependencias:  pip install numpy cvxpy pyserial matplotlib
===============================================================================
"""

import time
import sys
import csv

import numpy as np
import cvxpy as cp
import serial

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ============================================================================
# PARAMETROS DO USUARIO
# ============================================================================
PORT        = "COM7"     # porta serial do Arduino (ex.: "COM3", "/dev/ttyACM0")
BAUD        = 115200

T           = 100         # janela T (numero de amostras do experimento)
AMP_ENTRADA = 100       # amplitude do desvio de entrada du [% de potencia]
AMP_ESTADO  = 300.0        # amplitude maxima esperada do desvio de estado [C]
                         # (usada como verificacao de qualidade dos dados --
                         #  Assumption 5: excursoes grandes => resto d(k) grande)
RHO         = 0.95       # margem de estabilidade (disco de raio rho < 1)
DT          = 0.5       # taxa de amostragem [s]  (planta termica: 3 a 8 s)

UBAR        = 0       # entrada de equilibrio [%] (ponto de operacao aquecido)
SETTLE_S    = 1        # tempo de assentamento em ubar [s] (>= 10 min p/ TCLab)
TSP         = 200       # setpoint do controle [C]; None => usa o Tbar medido
CTRL_S      = 300        # duracao do controle em malha fechada [s] (0 = infinito)
SEED        = 0          # semente do gerador de excitacao

numeroEstados = 1        # n (SISO: estado = desvio de T1)
numeroInputs  = 1        # m (entrada = desvio de Q1)

# ============================================================================
# COMUNICACAO SERIAL
# ============================================================================
def open_serial():
    ser = serial.Serial(PORT, BAUD, timeout=max(3.0, 3 * DT))
    time.sleep(2.5)                      # o Uno reseta ao abrir a porta
    ser.reset_input_buffer()
    return ser

def send(ser, line):
    ser.write((line + "\n").encode("ascii"))

def read_line(ser):
    raw = ser.readline().decode("ascii", errors="ignore").strip()
    return raw

def wait_for(ser, prefix, echo=False, timeout_s=None):
    """Le linhas ate encontrar uma que comece com `prefix`. Repassa ERR."""
    t_start = time.time()
    while True:
        line = read_line(ser)
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

# ============================================================================
# 1. GERACAO DO VETOR DE EXCITACAO (perto do equilibrio -- Assumption 5)
# ============================================================================
np.random.seed(SEED)
du = np.random.uniform(-AMP_ENTRADA, AMP_ENTRADA, T)

print("=" * 70)
print(" Controle data-driven no TCLab (SISO: Q1 -> T1)")
print("=" * 70)
print(f" T = {T} | dt = {DT} s | amp_entrada = {AMP_ENTRADA} % | "
      f"amp_estado = {AMP_ESTADO} C | rho = {RHO}")
print(f" ubar = {UBAR} % | assentamento = {SETTLE_S} s | controle = {CTRL_S} s")
print(f" duracao do experimento: {T * DT:.0f} s")

ser = open_serial()
print(f"\n[1] Conectado em {PORT}. Enviando configuracao...")

send(ser, f"CFG,{T},{int(DT * 1000)},{UBAR:.3f},{SETTLE_S}")
wait_for(ser, "ACK,CFG", timeout_s=10)

for k in range(T):
    send(ser, f"U,{k},{du[k]:.4f}")
    wait_for(ser, f"ACK,U,{k}", timeout_s=5)
print(f"    Vetor de entrada ({T} amostras) enviado e confirmado.")

# ============================================================================
# 2. ASSENTAMENTO NO EQUILIBRIO + EXPERIMENTO (coleta via serial)
# ============================================================================
print(f"\n[2] Assentando a planta em ubar = {UBAR}% por {SETTLE_S} s...")
send(ser, "GO")
wait_for(ser, "ACK,GO", timeout_s=5)

Tbar = None
try:
    while True:
        line = read_line(ser)
        if line == "":
            continue
        if line.startswith("S,"):
            _, t_s, T1 = line.split(",")
            print(f"    assentando... t = {t_s:>4} s | T1 = {T1} C", end="\r")
        elif line.startswith("EQ,"):
            Tbar = float(line.split(",")[1])
            print(f"\n    Equilibrio medido: Tbar = {Tbar:.3f} C  (ubar = {UBAR}%)")
            break
        elif line.startswith("ERR"):
            raise RuntimeError(f"Arduino reportou erro: {line}")
except KeyboardInterrupt:
    send(ser, "X"); ser.close(); sys.exit("\nAbortado pelo usuario.")

print(f"\n[3] Experimento em andamento ({T} passos de {DT} s)...")
x_raw = np.zeros(T + 1)          # T1 absoluto: x(0)..x(T)
u_raw = np.zeros(T)              # u APLICADO (com saturacao): u(0)..u(T-1)
try:
    while True:
        line = read_line(ser)
        if line == "":
            continue
        if line.startswith("D,"):
            parts = line.split(",")
            k = int(parts[1])
            x_raw[k] = float(parts[2])
            if parts[3] != "nan":
                u_raw[k] = float(parts[3])
            print(f"    k = {k:>3}/{T} | T1 = {parts[2]} C | u = {parts[3]} %",
                  end="\r")
        elif line.startswith("WAITK"):
            print("\n    Coleta concluida. Arduino aguardando K (segurando ubar).")
            break
        elif line.startswith("ERR"):
            raise RuntimeError(f"Arduino reportou erro: {line}")
except KeyboardInterrupt:
    send(ser, "X"); ser.close(); sys.exit("\nAbortado pelo usuario.")

# ============================================================================
# 3. MONTAGEM DE X0, X1, U0 (desvios em torno do equilibrio)
# ============================================================================
dx = x_raw - Tbar                          # desvio de estado [C]
X0 = dx[0:T].reshape(numeroEstados, T)     # x(0) ... x(T-1)
X1 = dx[1:T + 1].reshape(numeroEstados, T) # x(1) ... x(T)
U0 = (u_raw - UBAR).reshape(numeroInputs, T)  # desvio de entrada APLICADO

n_sat = int(np.sum((u_raw <= 0.0) | (u_raw >= 100.0)))
if n_sat > 0:
    print(f"    AVISO: {n_sat} amostras saturaram em 0/100%. U0 usa o valor"
          " aplicado (correto), mas considere reduzir AMP_ENTRADA.")

exc_max = np.max(np.abs(dx))
print(f"\n[4] Excursao maxima do estado: |dx|_max = {exc_max:.3f} C "
      f"(limite amp_estado = {AMP_ESTADO} C)")
if exc_max > AMP_ESTADO:
    print("    AVISO: excursao acima de amp_estado -- os dados podem violar a"
          " hipotese de resto pequeno (Assumption 5). Sugestoes: reduzir"
          " AMP_ENTRADA, reduzir DT ou aumentar SETTLE_S.")

# --- persistencia de excitacao: rank([U0; X0]) == n + m ---
rank = np.linalg.matrix_rank(np.vstack([U0, X0]))
print(f"    rank([U0; X0]) = {rank}  (necessario n+m = "
      f"{numeroEstados + numeroInputs})")
assert rank == numeroEstados + numeroInputs, \
    "Dados nao persistentemente excitantes; aumente T ou AMP_ENTRADA."

# --- diagnostico do resto d(k) (proxy da Assumption 5) ---
# A planta e desconhecida: nao ha (A_lin, B_lin) para calcular D0 exato.
# Usamos o residuo do melhor ajuste linear (Teorema 1) como ESTIMATIVA,
# apenas para diagnostico -- o projeto de K continua 100% data-driven.
S = np.vstack([U0, X0])
BA_hat = X1 @ np.linalg.pinv(S)
D0_hat = X1 - BA_hat @ S
gamma_hat = (np.max(np.linalg.eigvals(D0_hat @ D0_hat.T).real) /
             np.min(np.linalg.eigvals(X1 @ X1.T).real))
print(f"    gamma estimado (proxy Assumption 5) ~ {gamma_hat:.2e}")

# ============================================================================
# 4. LMI DATA-DRIVEN (Teorema 6) COM MARGEM rho
#      [ rho^2 (X0 Q)   X1 Q ]
#      [ (X1 Q)'        X0 Q ]  > 0 ,   X0 Q > 0
#    K = U0 Q (X0 Q)^-1  -- projetado SO com dados (nao usa modelo).
#    A margem rho < 1 forca |eig(A+BK)| < rho, dando robustez ao resto d
#    (mesmo papel do alpha no Teorema 6).
# ============================================================================
print(f"\n[5] Resolvendo a LMI data-driven (rho = {RHO})...")
Q   = cp.Variable((T, numeroEstados))
X0Q = X0 @ Q
X1Q = X1 @ Q

lmi = cp.bmat([[RHO**2 * X0Q, X1Q],
               [X1Q.T,        X0Q]])
constraints = [
    lmi >> 1e-6 * np.eye(2 * numeroEstados),
    X0Q >> 1e-6 * np.eye(numeroEstados),
]
prob = cp.Problem(cp.Minimize(0), constraints)
try:
    prob.solve(solver=cp.CLARABEL)
except Exception:
    prob.solve(solver=cp.SCS)
print(f"    LMI solve status: {prob.status}")
if prob.status not in ("optimal", "optimal_inaccurate"):
    send(ser, "X"); ser.close()
    sys.exit("LMI infactivel -- revise os dados/parametros.")

Qv = Q.value
K = (U0 @ Qv) @ np.linalg.inv(X0 @ Qv)      # 1x1 no caso SISO
Kg = float(K[0, 0])
print(f"    Ganho data-driven K = {Kg:.5f}  [%/C]")

# ============================================================================
# 5. VERIFICACAO DE ESTABILIDADE DATA-DRIVEN (sem A, B): Acl = X1 GK
# ============================================================================
GK = Qv @ np.linalg.inv(X0 @ Qv)
eig_data = np.linalg.eigvals(X1 @ GK)
print(f"\n[6] |autoval.| (dados): {np.round(np.abs(eig_data), 4)}"
      f" | estavel: {np.all(np.abs(eig_data) < 1)}"
      f" | dentro da margem rho: {np.all(np.abs(eig_data) < RHO)}")
assert np.all(np.abs(eig_data) < 1.0), \
    "Verificacao data-driven falhou: malha fechada instavel."

# ============================================================================
# 6. ENVIO DE K E CONTROLE EM TEMPO REAL (streaming via serial)
# ============================================================================
Tsp_eff = Tbar if TSP is None else float(TSP)
if TSP is not None and abs(Tsp_eff - Tbar) > AMP_ESTADO:
    print(f"    AVISO: |Tsp - Tbar| = {abs(Tsp_eff - Tbar):.2f} C > amp_estado."
          " Realimentacao de estados pura tera offset em regime; o ganho foi"
          " validado localmente em torno de Tbar.")

print(f"\n[7] Enviando K ao Arduino. Setpoint = {Tsp_eff:.2f} C, "
      f"duracao = {CTRL_S} s. (Ctrl+C aborta)")
send(ser, f"K,{Kg:.6f},{Tsp_eff:.3f},{CTRL_S}")
wait_for(ser, "ACK,K", timeout_s=5)

t_log, T1_log, u_log = [], [], []
try:
    while True:
        line = read_line(ser)
        if line == "":
            continue
        if line.startswith("C,"):
            _, t_s, T1, u = line.split(",")
            t_log.append(float(t_s)); T1_log.append(float(T1)); u_log.append(float(u))
            print(f"    t = {float(t_s):>7.1f} s | T1 = {float(T1):6.2f} C | "
                  f"u = {float(u):6.2f} % | erro = {float(T1) - Tsp_eff:+.2f} C",
                  end="\r")
        elif line.startswith("END"):
            print("\n    Controle encerrado pelo Arduino.")
            break
        elif line.startswith("ERR"):
            raise RuntimeError(f"Arduino reportou erro: {line}")
except KeyboardInterrupt:
    print("\n    Abortando: desligando aquecedores...")
    send(ser, "X")
    try:
        wait_for(ser, "END", timeout_s=5)
    except Exception:
        pass
finally:
    ser.close()

# ============================================================================
# 7. SALVAMENTO DOS DADOS E GRAFICOS
# ============================================================================
with open("dados_experimento.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["k", "T1_C", "u_aplicado_pct", "dx_C", "du_aplicado_pct"])
    for k in range(T):
        w.writerow([k, x_raw[k], u_raw[k], dx[k], u_raw[k] - UBAR])
    w.writerow([T, x_raw[T], "", dx[T], ""])

with open("dados_controle.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_s", "T1_C", "u_pct"])
    for row in zip(t_log, T1_log, u_log):
        w.writerow(row)

fig, ax = plt.subplots(2, 2, figsize=(12, 7))
ke = np.arange(T + 1) * DT
ax[0, 0].plot(ke, x_raw, ".-")
ax[0, 0].axhline(Tbar, color="k", lw=0.7, ls="--", label=r"$\bar{T}$")
ax[0, 0].set_title("Experimento: T1"); ax[0, 0].set_ylabel("T1 [°C]")
ax[0, 0].legend(); ax[0, 0].grid(alpha=0.3)
ax[1, 0].step(ke[:-1], u_raw, where="post", color="tab:red")
ax[1, 0].axhline(UBAR, color="k", lw=0.7, ls="--", label=r"$\bar{u}$")
ax[1, 0].set_title("Experimento: Q1 aplicado"); ax[1, 0].set_ylabel("u [%]")
ax[1, 0].set_xlabel("tempo [s]"); ax[1, 0].legend(); ax[1, 0].grid(alpha=0.3)

if t_log:
    ax[0, 1].plot(t_log, T1_log)
    ax[0, 1].axhline(Tsp_eff, color="k", lw=0.7, ls="--", label="setpoint")
    ax[0, 1].set_title(f"Malha fechada (K = {Kg:.3f} %/°C, ρ = {RHO})")
    ax[0, 1].set_ylabel("T1 [°C]"); ax[0, 1].legend(); ax[0, 1].grid(alpha=0.3)
    ax[1, 1].step(t_log, u_log, where="post", color="tab:red")
    ax[1, 1].axhline(UBAR, color="k", lw=0.7, ls="--", label=r"$\bar{u}$")
    ax[1, 1].set_title("Malha fechada: Q1"); ax[1, 1].set_ylabel("u [%]")
    ax[1, 1].set_xlabel("tempo [s]"); ax[1, 1].legend(); ax[1, 1].grid(alpha=0.3)

fig.suptitle("Controle data-driven do TCLab (De Persis & Tesi, Thm 6) — SISO Q1→T1")
fig.tight_layout()
fig.savefig("tclab_datadriven_resultado.png", dpi=120)
print("\nSalvos: dados_experimento.csv, dados_controle.csv,"
      " tclab_datadriven_resultado.png")
