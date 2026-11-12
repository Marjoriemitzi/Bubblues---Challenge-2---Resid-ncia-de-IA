#!/usr/bin/env python3
"""
scripts/plot_metricas_semana3.py
Gera gráficos visuais comparativos para o Relatório da Semana 3 (LLM x RAG).
Projeto: Bubbles - Challenge 2 (Residência em IA - TIC-IA / Grupo 10)
"""

import json
import os
import matplotlib.pyplot as plt
import numpy as np

os.makedirs("docs/img", exist_ok=True)

with open("docs/avaliacao/resultados_semana3_llm_rag.json", "r", encoding="utf-8") as f:
    data = json.load(f)

table = data["tabela_comparativa"]

# Estilo visual limpo e profissional
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 14,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 16
})

# =====================================================================
# GRÁFICO 1: Comparativo das 4 Configurações nas 4 Métricas Principais
# =====================================================================
labels = [
    "1. LLM Pura\n(Sem RAG)",
    "2. RAG sem LLM\n(Retrieval Puro)",
    "3. RAG Clássico\n(Naive RAG)",
    "4A. RAG Bubbles\n(Semana 2)",
    "4B. RAG Bubbles\n(Otimizado Sem 3)"
]

p3 = [float(row["Precision@3"].replace("%", "")) for row in table[:5]]
exist = [float(row["Locais Existem"].replace("%", "")) for row in table[:5]]
ground = [float(row["Fundamentação"].replace("%", "")) for row in table[:5]]
abst = [float(row["Abstenção Correta"].replace("%", "")) for row in table[:5]]

x = np.arange(len(labels))
width = 0.20

fig, ax = plt.subplots(figsize=(12, 6.5))

rects1 = ax.bar(x - 1.5*width, p3, width, label="Precision@3", color="#3b82f6")
rects2 = ax.bar(x - 0.5*width, exist, width, label="Locais Existem (Meta: 100%)", color="#10b981")
rects3 = ax.bar(x + 0.5*width, ground, width, label="Fundamentação (Meta: 100%)", color="#8b5cf6")
rects4 = ax.bar(x + 1.5*width, abst, width, label="Abstenção Correta (Meta: 100%)", color="#f59e0b")

ax.set_ylabel("Desempenho (%)")
ax.set_title("Comparação Sistemática das 4 Abordagens: LLM x RAG (Semana 3)", pad=15, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylim(0, 115)
ax.legend(loc="upper left", frameon=True)
ax.axhline(100, color="gray", linestyle="--", alpha=0.5, linewidth=1)

def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f"{height:.1f}%",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=8.5, fontweight="bold")

autolabel(rects1)
autolabel(rects2)
autolabel(rects3)
autolabel(rects4)

plt.tight_layout()
fig.savefig("docs/img/comparativo_4_testes_semana3.png", dpi=300)
plt.close(fig)
print("✅ Gráfico 1 salvo: docs/img/comparativo_4_testes_semana3.png")

# =====================================================================
# GRÁFICO 2: Trade-off de Latência (ms) vs Precisão vs Custo de Tokens
# =====================================================================
fig, ax1 = plt.subplots(figsize=(10, 5.5))

configs_short = ["LLM Pura", "RAG s/ LLM", "RAG Clássico", "RAG Bubbles (Sem 2)", "RAG Bubbles (Sem 3)"]
latencies = [int(row["Latência Média"].replace(" ms", "")) for row in table[:5]]
tokens = [int(row["Tokens Médios"]) for row in table[:5]]

color1 = "#dc2626"
ax1.set_xlabel("Configuração Arquitetural")
ax1.set_ylabel("Latência Média (ms)", color=color1, fontweight="bold")
bars = ax1.bar(configs_short, latencies, color=color1, alpha=0.6, width=0.45, label="Latência (ms)")
ax1.tick_params(axis="y", labelcolor=color1)
ax1.set_ylim(0, 1800)

for bar in bars:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, yval + 30, f"{yval} ms", ha="center", va="bottom", fontsize=9, color=color1, fontweight="bold")

ax2 = ax1.twinx()
color2 = "#2563eb"
ax2.set_ylabel("Tokens Médios de Inferência (LLM)", color=color2, fontweight="bold")
lines = ax2.plot(configs_short, tokens, color=color2, marker="o", linewidth=2.5, markersize=8, label="Tokens LLM")
ax2.tick_params(axis="y", labelcolor=color2)
ax2.set_ylim(0, 900)

for i, txt in enumerate(tokens):
    ax2.annotate(f"{txt} tokens", (configs_short[i], tokens[i]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9, color=color2, fontweight="bold")

plt.title("Trade-off de Performance: Latência de Resposta vs Custo de Inferência", pad=15, fontweight="bold")
plt.tight_layout()
fig.savefig("docs/img/tradeoff_latencia_custo_qualidade.png", dpi=300)
plt.close(fig)
print("✅ Gráfico 2 salvo: docs/img/tradeoff_latencia_custo_qualidade.png")

# =====================================================================
# GRÁFICO 3: Evolução das Métricas da Semana 2 para a Semana 3
# =====================================================================
fig, ax = plt.subplots(figsize=(9, 5))

etapas = [
    "Semana 2\n(Pesos Iniciais:\nwv=0.40, wd=0.25)",
    "Semana 3\n(Calibração Equilibrada:\nwv=0.45, wd=0.15)",
    "Semana 3 Refinada\n(Foco Semântico/Vibe:\nwv=0.50, wd=0.05)"
]

valores = [64.6, 75.0, 77.1]
cores = ["#94a3b8", "#3b82f6", "#10b981"]

bars3 = ax.bar(etapas, valores, color=cores, width=0.4)
ax.set_ylabel("Precision@3 (%)", fontweight="bold")
ax.set_ylim(0, 95)
ax.set_title("Evolução da Precisão de Recomendação (Precision@3): Semana 2 → Semana 3", pad=15, fontweight="bold")

for bar in bars3:
    y = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, y + 2, f"{y:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")

# Anotações de ganho
ax.annotate("+10.4 p.p.", xy=(1, 75.0), xytext=(0.5, 78),
            arrowprops=dict(facecolor="#2563eb", shrink=0.05, width=1.5, headwidth=6),
            ha="center", fontsize=10, fontweight="bold", color="#2563eb")

ax.annotate("+12.5 p.p. acumulado", xy=(2, 77.1), xytext=(1.5, 84),
            arrowprops=dict(facecolor="#059669", shrink=0.05, width=1.5, headwidth=6),
            ha="center", fontsize=10, fontweight="bold", color="#059669")

plt.tight_layout()
fig.savefig("docs/img/evolucao_metricas_semana2_vs_semana3.png", dpi=300)
plt.close(fig)
print("✅ Gráfico 3 salvo: docs/img/evolucao_metricas_semana2_vs_semana3.png")

print("\n🎉 Todos os gráficos gerados com sucesso em docs/img/!")

