from orchestrator.verificacao_nlu import verificar
from orchestrator.stubs import _request

BASE = {"cafe", "park", "restaurant", "garden", "bakery"}


def _ped(**over):
    p = {"id": "TC-01", "tipo_pedido": "Padrao", "query": "Quero um cafe calmo na Asa Sul sem escadas",
         "restricoes": {"acessibilidade": "yes", "ambiente": "tranquilo"}}
    p.update(over)
    return p


def _req(**over):
    r = _request("r", target_amenities=["cafe"], noise_tolerance="baixo",
                 spatial_constraints={"target_region": "Asa Sul", "max_radius_km": 3.0},
                 accessibility_requirements={"wheelchair_required": True, "elder_friendly": False, "pet_friendly": False},
                 search_vector_focus=["calmo", "leitura"], raw_query=None)
    r.update(over)
    return r


def _niveis(achados):
    return {(a.nivel, a.campo) for a in achados}


def test_saida_correta_nao_gera_achados():
    assert verificar(_ped(), _req(), BASE) == []


def test_detecta_acessibilidade_ruido_regiao_e_categoria_erradas():
    req = _req(noise_tolerance="indiferente", target_amenities=["park"],
               accessibility_requirements={"wheelchair_required": False, "elder_friendly": False, "pet_friendly": False},
               spatial_constraints={"target_region": "Lago Sul", "max_radius_km": 3.0})
    n = _niveis(verificar(_ped(), req, BASE))
    assert {("ERRO", "wheelchair_required"), ("ERRO", "noise_tolerance"), ("ERRO", "target_region"), ("ERRO", "target_amenities")} <= n


def test_categoria_fora_da_base_e_erro():
    assert ("ERRO", "target_amenities") in _niveis(verificar(_ped(), _req(target_amenities=["library_bookstore"]), BASE))


def test_acao_esperada_abster_e_ambiguo():
    fora = _ped(id="TC-18", tipo_pedido="Fora_De_Escopo", restricoes={})
    ok = _request("r", intent_valid=False, out_of_scope=True, out_of_scope_reason="frete", target_amenities=[])
    assert verificar(fora, ok, BASE) == []
    assert ("ERRO", "acao") in _niveis(verificar(fora, _req(), BASE))
    amb = _ped(id="TC-16", tipo_pedido="Ambiguo", restricoes={}, query="algo legal")
    assert ("ERRO", "acao") in _niveis(verificar(amb, _req(), BASE))
    assert not [a for a in verificar(amb, _req(clarification_needed="Que tipo?", target_amenities=["cafe"],
                accessibility_requirements={"wheelchair_required": False, "elder_friendly": False, "pet_friendly": False},
                spatial_constraints={"target_region": None, "max_radius_km": 3.0}, noise_tolerance="indiferente"), BASE) if a.nivel == "ERRO"]


def test_raw_query_preenchido_e_erro_e_foco_longo_pede_revisao():
    n = _niveis(verificar(_ped(), _req(raw_query="vazou", search_vector_focus=["x" * 60]), BASE))
    assert ("ERRO", "raw_query") in n and ("REVISAR", "search_vector_focus") in n
