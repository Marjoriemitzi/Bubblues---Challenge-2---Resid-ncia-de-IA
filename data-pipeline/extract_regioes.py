"""Baixa do OSM (Overpass) as regioes do DF: RAs, bairros, quadras e cidades.

Saida: data/raw/regioes.json. Rodar antes de load_regioes.py.
"""

import json
import time
from pathlib import Path

import requests

ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
CONSULTA = """
[out:json][timeout:120];
area["name"="Distrito Federal"]["admin_level"="4"]->.df;
(
 rel["boundary"="administrative"]["admin_level"~"^(8|9|10|11)$"](area.df);
 nwr["place"~"^(suburb|neighbourhood|quarter|town|city|village|city_block)$"]["name"](area.df);
);
out center tags;
"""
HEADERS = {"User-Agent": "pipeline-brasilia/1.0 (projeto-estudo)"}
TENTATIVAS = 4


def baixar():
    espera = 5
    for tentativa in range(1, TENTATIVAS + 1):
        for url in ENDPOINTS:
            try:
                r = requests.post(url, data={"data": CONSULTA}, headers=HEADERS, timeout=150)
                if r.status_code == 200:
                    return r.json()["elements"]
                print(f"{url}: HTTP {r.status_code}")
            except (requests.RequestException, ValueError) as erro:
                print(f"{url}: {type(erro).__name__}")
        print(f"Tentativa {tentativa}/{TENTATIVAS} falhou; aguardando {espera}s")
        time.sleep(espera)
        espera *= 2
    raise RuntimeError("Overpass indisponivel; tente novamente mais tarde.")


def main():
    destino = Path("data/raw/regioes.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    elementos = baixar()
    destino.write_text(json.dumps({"elements": elementos}, ensure_ascii=False), encoding="utf-8")
    print(f"{len(elementos)} elementos salvos em {destino}")


if __name__ == "__main__":
    main()
