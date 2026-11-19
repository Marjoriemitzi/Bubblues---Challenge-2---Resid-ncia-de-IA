#!/usr/bin/env python3
"""Fase F: roda uma configuracao do Retrieval N vezes sobre o dataset (um run no Langfuse por repeticao).

  python scripts/avaliacao/rodar_matriz.py flash --repeticoes 3
  python scripts/avaliacao/rodar_matriz.py pipeline --repeticoes 1

Cada repeticao chama rodar_experimento.py com o nome f-<config>-r<k> e imprime uma linha de resumo.
O agente roda CRU (--sem-fallback) para medir o proprio agente; o resultado de cada run fica em
docs/avaliacao/resultado_f-<config>-r<k>.json.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AV = RAIZ / "docs" / "avaliacao"
CONFIGS = {
    "pipeline": dict(args=["--modo", "pipeline"], env={}),
    "flash": dict(args=["--modo", "llm", "--sem-fallback"], env={}),
    "flash-strict": dict(args=["--modo", "llm", "--sem-fallback"], env={"DEEPSEEK_STRICT": "1"}),
    "flash-thinking": dict(args=["--modo", "llm", "--sem-fallback"], env={"DEEPSEEK_REASONING_EFFORT": "high"}),
    "flash-prompt2": dict(args=["--modo", "llm", "--sem-fallback", "--prompt", "v2"], env={}),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", choices=sorted(CONFIGS))
    ap.add_argument("--repeticoes", type=int, default=3)
    a = ap.parse_args()
    cfg = CONFIGS[a.config]
    for k in range(1, a.repeticoes + 1):
        nome = f"f-{a.config}-r{k}"
        t0 = time.time()
        env = {**os.environ, **cfg["env"]}
        r = subprocess.run([sys.executable, "-u", str(RAIZ / "scripts" / "avaliacao" / "rodar_experimento.py"), *cfg["args"], "--nome", nome],
                           cwd=RAIZ / "data-pipeline", env=env, capture_output=True, text=True)
        saida = AV / f"resultado_{nome}.json"
        if r.returncode != 0 or not saida.exists():
            print(f"{nome}: FALHOU (rc={r.returncode})\n{r.stderr[-600:]}", flush=True)
            continue
        rs = json.loads(saida.read_text(encoding="utf-8"))["run_scores"]
        erros_api = r.stdout.count("API error") + r.stderr.count("API error")
        print(f"{nome}: {time.time()-t0:5.0f}s | P@3={rs['media_p_at_3']:.3f} nDCG@3={rs['media_ndcg_at_3']:.3f} "
              f"cob={rs['media_cobertura_rotulos']:.2f} lat={rs['media_latencia_s']:.1f}s fallbacks={rs.get('total_fallbacks', '-')} "
              f"tok={rs.get('media_tokens_prompt', 0):.0f}/{rs.get('media_tokens_saida', 0):.0f} erros_api_langfuse={erros_api}", flush=True)


if __name__ == "__main__":
    main()
