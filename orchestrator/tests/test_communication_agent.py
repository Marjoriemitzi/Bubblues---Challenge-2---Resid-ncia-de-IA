"""CommunicationAgent (LLM): fundamentacao da resposta, avisos obrigatorios e fallback. Sem rede (LLMFalso)."""

import pytest

from orchestrator.communication_agent import CommunicationAgent, criar_comunicacao, montar_fatos, verificar
from orchestrator.llm_client import LLMError
from orchestrator.llm_fake import LLMFalso, texto

LINK1, LINK2 = "https://www.openstreetmap.org/node/1", "https://www.openstreetmap.org/node/2"


def estado(horario=None, expandido=False, notas1=None):
    ev = lambda pid, nome, link, score, notas: {
        "place_id": pid, "place_name": nome, "total_score": score, "integrity_test": {"passed": True},
        "osm_reference": {"osm_link": link}, "grounding_notes": notas, "matched_tags": ["amenity=cafe"]}
    return {
        "structured_request": {"out_of_scope": False, "impossible_criteria": False, "clarification_needed": None,
                               "spatial_constraints": {"max_radius_km": 3.0},
                               "temporal_constraints": {"preferred_time_slot": None, "specific_hours": horario}},
        "search_response": {"applied_filters": {"radius_km": 6.0 if expandido else 3.0, "expanded_once": expandido},
                            "items": [{"place_id": "1", "distance_km": 1.234, "address": None},
                                      {"place_id": "2", "distance_km": 2.5, "address": "SQN 1"}]},
        "evidence_records": [ev("1", "Cafe Alfa", LINK1, 0.9, notas1 or ["Acessibilidade: wheelchair=yes."]),
                             ev("2", "Cafe Beta", LINK2, 0.8, ["Horário de funcionamento: Mo-Su 08:00-22:00 (compatível com o pedido)."])],
    }


BOA = f"Cafe Alfa fica a 1.23 km e e acessivel. {LINK1}\nCafe Beta, a 2.5 km, abre cedo. {LINK2}"


def test_resposta_fundamentada_passa():
    llm = LLMFalso(texto(BOA))
    r = CommunicationAgent(llm)(estado())
    assert r["final_response"] == BOA and "tentativas=1" in r["note"]
    assert "Cafe Alfa" in llm.mensagens_recebidas[0][1]["content"]  # o modelo recebe so os fatos


def test_url_inventada_e_rejeitada_e_o_modelo_corrige():
    ruim = BOA + " Veja tambem https://exemplo.com/x"
    llm = LLMFalso(texto(ruim), texto(BOA))
    r = CommunicationAgent(llm)(estado())
    assert r["final_response"] == BOA and "tentativas=2" in r["note"]
    assert "URL que nao esta" in llm.mensagens_recebidas[1][-1]["content"]


def test_distancia_inventada_e_rejeitada():
    assert "nao existe nos dados" in verificar(BOA.replace("2.5 km", "9 km"), montar_fatos(estado()))


def test_lugar_ou_link_faltando_e_rejeitado():
    assert "falta" in verificar(f"So o Cafe Alfa {LINK1}", montar_fatos(estado()))


def test_aviso_de_raio_e_obrigatorio():
    f = montar_fatos(estado(expandido=True))
    assert [a["tipo"] for a in f["avisos"]] == ["raio"] and "6 km" in f["avisos"][0]["texto"]
    assert "raio" in verificar(BOA, f)
    assert verificar(BOA + " Ampliei o raio para 6 km.", f) is None


def test_aviso_de_horario_so_para_quem_nao_tem_horario_no_osm():
    f = montar_fatos(estado(horario="ate 22h"))
    assert [a["tipo"] for a in f["avisos"]] == ["horario"]
    assert "Cafe Alfa" in f["avisos"][0]["texto"] and "Cafe Beta" not in f["avisos"][0]["texto"]
    assert montar_fatos(estado())["avisos"] == []


def test_fallback_quando_o_llm_falha_mantem_os_avisos():
    r = CommunicationAgent(LLMFalso(LLMError("fora do ar")))(estado(expandido=True))
    assert "Cafe Alfa" in r["final_response"] and LINK1 in r["final_response"]
    assert "Avisos:" in r["final_response"] and "6 km" in r["final_response"]
    assert "formatador" in r["note"] and "LLMError" in r["note"]


def test_fallback_quando_o_modelo_reprova_sempre():
    llm = LLMFalso(texto("sem links"), texto("sem links"))
    r = CommunicationAgent(llm)(estado())
    assert LINK2 in r["final_response"] and "formatador" in r["note"]


@pytest.mark.parametrize("req", [
    {"out_of_scope": True, "out_of_scope_reason": "frete"},
    {"impossible_criteria": True, "impossible_criteria_reason": "Narnia"},
    {"clarification_needed": "Prefere tranquilo?"},
])
def test_desvios_nao_chamam_o_llm(req):
    llm = LLMFalso()
    s = {"structured_request": req}
    r = CommunicationAgent(llm)(s)
    assert r["final_response"] and llm.chamadas == 0


def test_sem_evidencia_aprovada_nao_chama_o_llm():
    s = estado()
    s["evidence_records"] = []
    llm = LLMFalso()
    assert "evidências suficientes" in CommunicationAgent(llm)(s)["final_response"] and llm.chamadas == 0


def test_modo_deterministico_e_invalido():
    from orchestrator.communication import communication_agent
    assert criar_comunicacao("deterministic") is communication_agent
    with pytest.raises(ValueError):
        criar_comunicacao("xyz")
    assert isinstance(criar_comunicacao("llm", llm=LLMFalso()), CommunicationAgent)


def test_grafo_padrao_usa_o_communication_agent(monkeypatch):
    from orchestrator.graph import COMMUNICATION, run
    from orchestrator.retrieval_factory import montar_grafo
    from orchestrator.stubs import stub_nlu, stub_retrieval

    monkeypatch.setenv("COMMUNICATION_MODE", "deterministic")
    g = montar_grafo(stub_nlu(), None, "deterministic")
    assert COMMUNICATION in g.get_graph().nodes
    monkeypatch.delenv("COMMUNICATION_MODE")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("orchestrator.llm_client.load_dotenv", lambda *a, **k: None, raising=False)
    from orchestrator.communication import communication_agent
    # sem chave e sem pedir llm: degrada para o formatador em vez de quebrar
    import orchestrator.communication_agent as ca
    from orchestrator.llm_client import LLMError

    def sem_chave():
        raise LLMError("sem chave")
    monkeypatch.setattr("orchestrator.llm_client.LLMClient", lambda *a, **k: sem_chave())
    assert ca.criar_comunicacao() is communication_agent
    monkeypatch.setenv("COMMUNICATION_MODE", "llm")
    with pytest.raises(LLMError):
        ca.criar_comunicacao()
