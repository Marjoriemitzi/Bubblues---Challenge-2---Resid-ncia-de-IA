import json
import sqlite3
from agente_entrada_nlu import IntakeNLUAgent
from agente_validador import ValidationAgent

nlu_agent = IntakeNLUAgent(max_retries=3)
val_agent = ValidationAgent(db_path="banco_inicial.db")

print("=" * 75)
print("🧪 PARTE 1: TESTES DE ACEITE DO AGENTE DE ENTRADA (CONTRATO 2)")
print("=" * 75)

cenarios_nlu = [
    (
        "Cenário 1 — Persona Dona Helena (Idosa + Cadeira de Rodas)",
        "Sou a Dona Helena, tenho 72 anos, uso cadeira de rodas e procuro um café calmo na Asa Norte à tarde com rampa acessível para conversar com amigas."
    ),
    (
        "Cenário 2 — Bloqueio Fora de Escopo (Frete Comercial)",
        "Preciso contratar um frete com caminhão baú para levar uma geladeira até Águas Claras."
    ),
    (
        "Cenário 3 — Bloqueio Critério Impossível (Horário Inviável 03h30)",
        "Quero um café silencioso aberto às 03h30 da madrugada no Plano Piloto para ler um livro."
    )
]

requisicao_dona_helena = None

for titulo, texto in cenarios_nlu:
    print(f"\n📌 {titulo}")
    print(f"   Entrada: \"{texto}\"")
    resultado = nlu_agent.processar_solicitacao(texto)
    if "Dona Helena" in titulo:
        requisicao_dona_helena = resultado
    print("   Saída Contrato 2 (JSON):")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

print("\n" + "=" * 75)
print("🛡️ PARTE 2: TESTES DE ACEITE DO VALIDATION_AGENT (ISSUE #04 - RNF01)")
print("=" * 75)

# Simulando 4 candidatos retornados pelo Retrieval_Agent para o pedido da Dona Helena
candidatos_retrieval = [
    {
        "nome": "Sebinho Livraria Café e Bistrô Asa Norte",
        "osm_id": "node/1849203941",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "score_contributions": {
            "semantic_similarity": 0.451200,
            "spatial_proximity": 0.250000,
            "accessibility_match": 0.200000,
            "noise_compatibility": 0.050000
        },
        "score_total": 0.951200  # Soma exata: |0.951200 - 0.951200| = 0.0 < 1e-5 (APROVADO)
    },
    {
        "nome": "Café Fantasma Gerado por Alucinação",
        "osm_id": None,  # Falha RNF01: sem osm_id
        "is_public_verified": False,
        "wheelchair": "yes",
        "elder_friendly": True,
        "score_contributions": {"semantic_similarity": 0.50, "spatial_proximity": 0.30},
        "score_total": 0.80
    },
    {
        "nome": "Bistrô Subsolo Escadaria Antiga",
        "osm_id": "node/9988776655",
        "is_public_verified": True,
        "wheelchair": "no",  # Falha Acessibilidade: Dona Helena exige wheelchair_required=True
        "elder_friendly": False,
        "score_contributions": {"semantic_similarity": 0.40, "spatial_proximity": 0.35},
        "score_total": 0.75
    },
    {
        "nome": "Ernesto Cafés Especiais Asa Sul",
        "osm_id": "way/4455667788",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True,
        "score_contributions": {
            "semantic_similarity": 0.420000,
            "spatial_proximity": 0.200000,
            "accessibility_match": 0.150000
        },
        "score_total": 0.890000  # Falha Matemática: soma real é 0.770000 (diferença 0.12 >= 1e-5)
    }
]

relatorio_auditoria = val_agent.auditar_lote(requisicao_dona_helena, candidatos_retrieval)

print(f"\n📊 Resumo da Auditoria para Request ID: {relatorio_auditoria['request_id']}")
print(f"   Total de Candidatos Auditados: {relatorio_auditoria['total_auditados']}")
print(f"   ✅ Candidatos Aprovados: {len(relatorio_auditoria['aprovados'])}")
for ap in relatorio_auditoria["aprovados"]:
    print(f"      -> {ap['candidate_name']} (osm_id: {ap['osm_id']} | Score: {ap['score_total']:.6f} | Erro Mat.: {ap['erro_matematico']:.8f})")

print(f"\n   ❌ Candidatos Reprovados: {len(relatorio_auditoria['reprovados'])}")
for rep in relatorio_auditoria["reprovados"]:
    print(f"      -> {rep['candidate_name']} (osm_id: {rep['osm_id']})")
    for motivo in rep["rejection_reasons"]:
        print(f"         • Motivo: {motivo}")
    print(f"         • Instrução ao Retrieval_Agent: {rep['retry_instruction']}")

# Conferindo persistência no banco SQLite (tabela evidencias_busca)
conn = sqlite3.connect("banco_inicial.db")
cur = conn.cursor()
cur.execute("SELECT evidence_id, candidate_name, approved, erro_matematico FROM evidencias_busca ORDER BY rowid DESC LIMIT 4")
linhas = cur.fetchall()
conn.close()

print("\n🗄️ Registros Persistidos na Tabela 'evidencias_busca':")
for ev_id, c_nome, aprov, erro_mat in linhas:
    status = "APROVADO" if aprov == 1 else "REPROVADO"
    print(f"   [{ev_id}] {c_nome} -> {status} (|Δ Score| = {erro_mat:.6f})")