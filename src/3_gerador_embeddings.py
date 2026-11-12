import json
from sentence_transformers import SentenceTransformer

print("⚙️ Carregando o modelo de embeddings local...")
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

with open("locais_enriquecidos.json", "r", encoding="utf-8") as f:
    locais = json.load(f)

for local in locais:
    print(f"📐 Vetorizando: {local['nome']}")
    vibe = local.get('vibe_estruturada', {})
    
    # Esta é a sua regra de P3: Unir as dimensões em um texto rico
    texto_base = (
        f"Local: {local['nome']}. "
        f"Vibe: {vibe.get('vibe_resumo', '')} "
        f"Ruído: {vibe.get('nivel_ruido', '')}. "
        f"Público: {vibe.get('publico_frequente', '')}. "
        f"Natureza: {vibe.get('pontuacao_natureza', 0)}. "
        f"Socialização: {vibe.get('pontuacao_socializacao', 0)}."
    )
    
    # Gera o vetor e converte de numpy array para lista nativa do Python
    vetor = model.encode(texto_base).tolist()
    
    local['vector'] = vetor
    local['texto_base_vetorizado'] = texto_base

with open("locais_vetorizados.json", "w", encoding="utf-8") as f:
    json.dump(locais, f, ensure_ascii=False, indent=4)

print("✅ Vetorização concluída! Arquivo locais_vetorizados.json gerado.")