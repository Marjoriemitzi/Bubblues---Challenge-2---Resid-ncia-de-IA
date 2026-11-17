import json
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer

print("🗄️ Criando Banco Inicial local (SQLite)...")
conn = sqlite3.connect("banco_inicial.db")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS role_explorador (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        cidade TEXT,
        vibe_json TEXT,
        texto_base TEXT,
        embedding TEXT
    );
""")
cur.execute("DELETE FROM role_explorador;")
conn.commit()

with open("locais_vetorizados.json", "r", encoding="utf-8") as f:
    locais = json.load(f)

if not locais:
    print("❌ ERRO: locais_vetorizados.json está vazio! Rode os scripts 1, 2 e 3 primeiro.")
    exit(1)

for local in locais:
    print(f"💾 Gravando no banco_inicial.db: {local['nome']}")
    cur.execute("""
        INSERT INTO role_explorador (nome, cidade, vibe_json, texto_base, embedding)
        VALUES (?, ?, ?, ?, ?)
    """, (
        local['nome'],
        local['cidade'],
        json.dumps(local.get('vibe_estruturada', {}), ensure_ascii=False),
        local.get('texto_base_vetorizado', ''),
        json.dumps(local.get('vector', []))
    ))

conn.commit()
print(f"✅ {len(locais)} locais salvos no banco de dados!\n")

# =====================================================================
# PROVA REAL DO PIPELINE: BUSCA VETORIAL (RAG) SOBRE O BANCO CRIADO
# =====================================================================
print("🔎 Iniciando Teste de Busca Semântica (RAG) no Banco Inicial...")
model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')

pedidos_usuarios = [
    "Quero um café calmo e silencioso para ler livros e conversar tranquilo",
    "Quero fazer caminhada ao ar livre em contato com a natureza e árvores"
]

cur.execute("SELECT nome, vibe_json, embedding FROM role_explorador")
registros_banco = cur.fetchall()

for pedido in pedidos_usuarios:
    print(f"\n🗣️ Pedido do Usuário: '{pedido}'")
    vetor_pedido = model.encode(pedido)
    
    ranking = []
    for nome, vibe_str, emb_str in registros_banco:
        vetor_local = np.array(json.loads(emb_str))
        # Cálculo exato da Similaridade de Cosseno
        similaridade = np.dot(vetor_pedido, vetor_local) / (
            np.linalg.norm(vetor_pedido) * np.linalg.norm(vetor_local)
        )
        vibe_obj = json.loads(vibe_str)
        ranking.append((similaridade, nome, vibe_obj))
    
    ranking.sort(key=lambda x: x[0], reverse=True)
    
    for pos, (score, nome, vibe) in enumerate(ranking, start=1):
        print(f"   #{pos} [{score:.4f}] {nome}")
        print(f"       Ruído: {vibe.get('nivel_ruido')} | Vibe: {vibe.get('vibe_resumo')}")

cur.close()
conn.close()