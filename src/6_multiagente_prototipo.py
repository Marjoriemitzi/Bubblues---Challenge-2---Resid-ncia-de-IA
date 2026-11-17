import json
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from agente_entrada_nlu import IntakeNLUAgent
from agente_validador import ValidationAgent

print("🤖 Inicializando Sistema Multiagentes (4 Agentes) — Projeto Bubbles\n")
model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")

OSM_METADATA_MAP = {
    "Sebinho Livraria Café e Bistrô Asa Norte": {
        "osm_id": "node/1849203941",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True
    },
    "Parque da Cidade Sarah Kubitschek": {
        "osm_id": "way/2938475610",
        "is_public_verified": True,
        "wheelchair": "yes",
        "elder_friendly": True
    },
    "Ernesto Cafés Especiais Asa Sul": {
        "osm_id": "node/4455667788",
        "is_public_verified": True,
        "wheelchair": "no",
        "elder_friendly": True
    }
}


class ResearchAgent:
    def __init__(self, db_path="banco_inicial.db"):
        self.db_path = db_path

    def buscar_candidatos(self, structured_request: dict) -> list:
        foco = structured_request["search_vector_focus"]
        ruido_desejado = structured_request.get("noise_tolerance")
        print(f"🔍 [2. Research_Agent] Vetorizando foco semântico: '{foco}'")

        vetor_q = model.encode(foco)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT nome, cidade, vibe_json, embedding FROM role_explorador")
        registros = cur.fetchall()
        conn.close()

        candidatos = []
        for nome, cidade, vibe_str, emb_str in registros:
            vetor_loc = np.array(json.loads(emb_str))
            sim = float(np.dot(vetor_q, vetor_loc) / (np.linalg.norm(vetor_q) * np.linalg.norm(vetor_loc)))
            vibe_obj = json.loads(vibe_str)
            meta_osm = OSM_METADATA_MAP.get(nome, {"osm_id": None, "is_public_verified": False, "wheelchair": "no", "elder_friendly": False})

            peso_sem = round(sim * 0.6, 6)
            peso_ruido = 0.200000 if vibe_obj.get("nivel_ruido") == ruido_desejado else 0.080000
            peso_acess = 0.200000 if meta_osm["wheelchair"] == "yes" else 0.000000
            score_total = round(peso_sem + peso_ruido + peso_acess, 6)

            candidatos.append({
                "nome": nome,
                "cidade": cidade,
                "vibe": vibe_obj,
                "osm_id": meta_osm["osm_id"],
                "is_public_verified": meta_osm["is_public_verified"],
                "wheelchair": meta_osm["wheelchair"],
                "elder_friendly": meta_osm["elder_friendly"],
                "score_contributions": {
                    "semantic_similarity": peso_sem,
                    "noise_compatibility": peso_ruido,
                    "accessibility_match": peso_acess
                },
                "score_total": score_total
            })

        candidatos.sort(key=lambda x: x["score_total"], reverse=True)
        print(f"   -> {len(candidatos)} candidatos recuperados do banco vetorial.")
        return candidatos


class CommunicationAgent:
    def responder(self, structured_request: dict, relatorio_validacao: dict) -> str:
        print("💬 [4. Communication_Agent] Adaptando resposta ao perfil do usuário...")
        aprovados = relatorio_validacao.get("aprovados", [])
        if not aprovados:
            return "Não encontramos locais que atendam 100% aos requisitos de segurança e acessibilidade solicitados."

        req_acess = structured_request.get("accessibility_requirements", {})
        saudacao = (
            "Olá! Selecionamos apenas locais públicos verificados no OpenStreetMap com acessibilidade para cadeira de rodas e conforto para idosos:\n"
            if req_acess.get("wheelchair_required")
            else "Olá! Confira os locais públicos verificados mais compatíveis com o seu pedido:\n"
        )

        linhas = [saudacao]
        for idx, item in enumerate(aprovados, start=1):
            linhas.append(
                f"  {idx}. {item['candidate_name']} (OSM: {item['osm_id']})\n"
                f"     • Score Auditado: {item['score_total']:.4f} | Evidência: {item['evidence_id']}"
            )
        return "\n".join(linhas)


def executar_pipeline_multiagente(pergunta: str):
    print("=" * 75)
    print(f"👤 ENTRADA DO USUÁRIO: \"{pergunta}\"")
    print("=" * 75)

    nlu = IntakeNLUAgent()
    research = ResearchAgent()
    validator = ValidationAgent()
    communicator = CommunicationAgent()

    # 1. Agente de Entrada (Contrato 2)
    print("🧠 [1. Intake_NLU_Agent] Extraindo Contrato 2 e verificando guardrails...")
    req = nlu.processar_solicitacao(pergunta)
    if not req["intent_valid"]:
        motivo = req["out_of_scope_reason"] or req["impossible_criteria_reason"]
        print(f"🛑 [1. Intake_NLU_Agent] Pedido bloqueado na entrada: {motivo}\n")
        return

    # 2. Agente de Pesquisa (RAG)
    candidatos = research.buscar_candidatos(req)

    # 3. Agente de Validação (Issue #04 - RNF01)
    print("🛡️ [3. Validation_Agent] Auditando RNF01, acessibilidade e soma matemática...")
    auditoria = validator.auditar_lote(req, candidatos)
    print(f"   -> Aprovados: {len(auditoria['aprovados'])} | Reprovados: {len(auditoria['reprovados'])}")
    for rep in auditoria["reprovados"]:
        print(f"   -> [REPROVADO] {rep['candidate_name']}: {rep['rejection_reasons'][0]}")

    # 4. Agente de Comunicação
    resposta_final = communicator.responder(req, auditoria)
    print("\n✅ RESPOSTA ENTREGUE AO USUÁRIO:\n" + resposta_final + "\n")


if __name__ == "__main__":
    executar_pipeline_multiagente(
        "Sou a Dona Helena, uso cadeira de rodas e quero um café calmo e silencioso na Asa Norte para ler e conversar à tarde."
    )
    executar_pipeline_multiagente(
        "Preciso contratar um frete de caminhão para mudança em Taguatinga."
    )
