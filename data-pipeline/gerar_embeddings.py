"""Gera e grava os embeddings da tabela places. Rodar depois de curadoria.sql."""

import argparse

from busca import DIMENSAO_EMBEDDING, conectar, vetor_para_texto

MODELO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

ETIQUETAS_DESCRITIVAS = (
    "description",
    "cuisine",
    "sport",
    "diet:vegan",
    "diet:vegetarian",
    "outdoor_seating",
    "internet_access",
    "wheelchair",
    "addr:suburb",
)


def texto_do_lugar(nome, categoria, tags):
    """Monta o texto do lugar. Sempre com os mesmos campos, na mesma ordem."""
    partes = [f"nome: {nome}", f"categoria: {categoria}"]
    partes += [f"{c}: {tags[c]}" for c in ETIQUETAS_DESCRITIVAS if c in tags]
    return ". ".join(partes)


def carregar_modelo():
    from sentence_transformers import SentenceTransformer

    modelo = SentenceTransformer(MODELO)
    dimensao = modelo.get_embedding_dimension()
    if dimensao != DIMENSAO_EMBEDDING:
        raise RuntimeError(f"{MODELO} gera {dimensao} dimensoes; o banco espera {DIMENSAO_EMBEDDING}.")
    return modelo


def gerar_embedding_consulta(texto, modelo=None):
    modelo = modelo or carregar_modelo()
    return modelo.encode(texto, normalize_embeddings=True).tolist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--todos", action="store_true", help="Refaz tambem os que ja tem embedding.")
    parser.add_argument("--lote", type=int, default=64)
    args = parser.parse_args()

    filtro = "" if args.todos else "WHERE embedding IS NULL"
    with conectar() as conexao:
        linhas = conexao.execute(
            f"SELECT place_id, nome, categoria, tags FROM places {filtro} ORDER BY place_id"
        ).fetchall()
        if not linhas:
            print("Nenhum lugar para processar.")
            return

        modelo = carregar_modelo()
        for inicio in range(0, len(linhas), args.lote):
            lote = linhas[inicio:inicio + args.lote]
            textos = [texto_do_lugar(nome, categoria, tags) for _, nome, categoria, tags in lote]
            vetores = modelo.encode(textos, normalize_embeddings=True, batch_size=args.lote)
            with conexao.transaction(), conexao.cursor() as cursor:
                cursor.executemany(
                    "UPDATE places SET embedding = %s::vector WHERE place_id = %s",
                    [
                        (vetor_para_texto(vetor), linha[0])
                        for vetor, linha in zip(vetores.tolist(), lote)
                    ],
                )
            print(f"{inicio + len(lote)}/{len(linhas)} lugares processados")


if __name__ == "__main__":
    main()
