"""Carrega data/raw/regioes.json na tabela `regioes` (substitui o conteudo anterior)."""

import json
from pathlib import Path

from busca import conectar
from regioes import elementos_para_linhas

COLUNAS = ("nome", "nome_normalizado", "tipo", "prioridade", "osm_id", "osm_type", "latitude", "longitude")


def carregar(conexao, linhas):
    with conexao.transaction(), conexao.cursor() as cursor:
        cursor.execute("TRUNCATE regioes RESTART IDENTITY")
        cursor.executemany(
            f"INSERT INTO regioes ({', '.join(COLUNAS)}) VALUES ({', '.join('%s' for _ in COLUNAS)})",
            [tuple(linha[c] for c in COLUNAS) for linha in linhas],
        )
    return len(linhas)


def main():
    arquivo = Path("data/raw/regioes.json")
    if not arquivo.exists():
        raise FileNotFoundError("Execute extract_regioes.py primeiro.")
    linhas = elementos_para_linhas(json.loads(arquivo.read_text(encoding="utf-8"))["elements"])
    if not linhas:
        raise ValueError("Nenhuma regiao valida no arquivo.")
    with conectar() as conexao:
        print(f"{carregar(conexao, linhas)} regioes carregadas.")


if __name__ == "__main__":
    main()
