import os
import sys
import json
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("TAVILY_API_KEY")

if not api_key or "sua_chave" in api_key:
    print("❌ ERRO: Coloque uma TAVILY_API_KEY válida no arquivo .env e salve (Cmd+S)!")
    sys.exit(1)

tavily_client = TavilyClient(api_key=api_key.strip())

locais_sementes = [
    "Ernesto Cafés Especiais Asa Sul Brasília avaliações ambiente",
    "Parque da Cidade Sarah Kubitschek Brasília avaliações caminhada",
    "Sebinho Livraria Café e Bistrô Asa Norte Brasília avaliações"
]

resultados = []

for query in locais_sementes:
    print(f"🔍 Buscando na web: {query}")
    try:
        response = tavily_client.search(query=query, search_depth="advanced", max_results=4)
        textos_encontrados = [r['content'] for r in response.get('results', []) if r.get('content')]
        
        nome_local = query.split(" Brasília")[0]
        print(f"   -> {len(textos_encontrados)} trechos extraídos para '{nome_local}'")
        
        if textos_encontrados:
            resultados.append({
                "nome": nome_local,
                "cidade": "Brasília",
                "reviews": textos_encontrados
            })
    except Exception as e:
        print(f"❌ Erro ao buscar {query}: {e}")

if not resultados:
    print("❌ Nenhum dado foi extraído. Verifique sua chave TAVILY_API_KEY no .env.")
    sys.exit(1)

with open("locais_brutos.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=4)

print(f"✅ Extração concluída! {len(resultados)} locais salvos em locais_brutos.json.")