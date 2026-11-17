import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

with open("locais_brutos.json", "r", encoding="utf-8") as f:
    locais = json.load(f)

if not locais:
    print("❌ ERRO: locais_brutos.json está vazio! Rode o script 1 primeiro.")
    sys.exit(1)

def classificar_por_regras_locais(nome: str, texto: str) -> dict:
    """Classificador determinístico local (Tabela de Regras P3) sobre os textos extraídos da web."""
    t = (nome + " " + texto).lower()

    # 1. Nível de ruído
    if any(k in t for k in ["silencioso", "calmo", "tranquilo", "leitura", "livraria", "sebinho", "estudar"]):
        ruido = "Baixo"
    elif any(k in t for k in ["barulhento", "agitado", "música alta", "lotado", "balada"]):
        ruido = "Alto"
    else:
        ruido = "Moderado"

    # 2. Pontuação de natureza (0.0 a 1.0)
    pontos_nat = sum(1 for k in ["parque", "árvores", "ar livre", "natureza", "caminhada", "verde", "lago", "grama"] if k in t)
    pontuacao_natureza = round(min(1.0, max(0.1, pontos_nat * 0.25)), 2)

    # 3. Pontuação de socialização (0.0 a 1.0)
    pontos_soc = sum(1 for k in ["conversa", "amigos", "encontro", "café", "bistrô", "mesas", "convivência", "família", "grupo"] if k in t)
    pontuacao_socializacao = round(min(1.0, max(0.4, 0.5 + pontos_soc * 0.1)), 2)

    # 4. Acessibilidade e público
    acessivel = any(k in t for k in ["acessível", "cadeirante", "rampa", "plano", "amplo", "parque"])
    publico = "Misto"

    # 5. Resumo da vibe baseado nas evidências encontradas
    if pontuacao_natureza >= 0.6:
        resumo = "Espaço amplo ao ar livre com forte contato com a natureza, ideal para caminhadas e encontros descontraídos em grupo."
    elif ruido == "Baixo":
        resumo = "Ambiente acolhedor e tranquilo, propício para leitura, conversas calmas e encontros em pequenos grupos."
    else:
        resumo = "Ambiente urbano agradável e convidativo para socialização, cafés e conversas em grupo."

    return {
        "vibe_resumo": resumo,
        "nivel_ruido": ruido,
        "acessibilidade_provavel": acessivel,
        "publico_frequente": publico,
        "pontuacao_natureza": pontuacao_natureza,
        "pontuacao_socializacao": pontuacao_socializacao
    }

prompt_sistema = """Você é um classificador de ambientes para um sistema de recomendação de encontros presenciais.
Leia os relatos sobre o local e retorne APENAS um objeto JSON válido com estas chaves exatas:
- vibe_resumo: (string) uma frase detalhando a atmosfera do local.
- nivel_ruido: (string) 'Baixo', 'Moderado' ou 'Alto'.
- acessibilidade_provavel: (boolean) true ou false.
- publico_frequente: (string) 'Jovens', 'Idosos' ou 'Misto'.
- pontuacao_natureza: (float de 0.0 a 1.0) nível de contato com natureza/ar livre.
- pontuacao_socializacao: (float de 0.0 a 1.0) adequação para conversar em grupo."""

for local in locais:
    texto_reviews = " ".join(local['reviews'])[:3500]
    usou_llm = False

    if api_key and "sua_chave" not in api_key:
        try:
            if api_key.startswith("gsk_"):
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                modelo = "llama-3.3-70b-versatile"
            else:
                client = OpenAI(api_key=api_key)
                modelo = "gpt-4o-mini"

            print(f"🧠 Extraindo vibe via LLM ({modelo}): {local['nome']}")
            response = client.chat.completions.create(
                model=modelo,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"Local: {local['nome']}\nRelatos da web: {texto_reviews}"}
                ]
            )
            local['vibe_estruturada'] = json.loads(response.choices[0].message.content)
            usou_llm = True
        except Exception as e:
            print(f"⚠️ API LLM indisponível/sem créditos ({type(e).__name__}). Aplicando Tabela de Regras Local (P3)...")

    if not usou_llm:
        local['vibe_estruturada'] = classificar_por_regras_locais(local['nome'], texto_reviews)

    print(f"   -> Vibe extraída: {local['vibe_estruturada'].get('vibe_resumo')}")

with open("locais_enriquecidos.json", "w", encoding="utf-8") as f:
    json.dump(locais, f, ensure_ascii=False, indent=4)

print("✅ Processamento concluído! Arquivo locais_enriquecidos.json gerado com sucesso.")