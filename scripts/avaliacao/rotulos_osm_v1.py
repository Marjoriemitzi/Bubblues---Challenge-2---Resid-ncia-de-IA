#!/usr/bin/env python3
"""Rotulos de relevancia (0/1/2) do pool de candidatos reais (OSM), por UM anotador (Claude).

Protocolo (mesma escala do gabarito v2):
  2 = atende o nucleo do pedido; 1 = alternativa aceitavel/parcial OU atributo central nao confirmado;
  0 = nao atende (tipo de lugar errado, horario/raio/bairro violados com evidencia).
  Penaliza -1 so com EVIDENCIA de violacao (horario do OSM, bairro explicito, distancia > raio do pedido).
Evidencia: web (pesquisa na internet) | osm (tags do banco) | tipo (so categoria/nome) | ref (conhecimento do anotador).
Confianca: A alta, M media, B baixa.

LIMITACOES (ver docs/avaliacao/gabarito_osm_v1.md): anotador unico e IA; nao cego (viu score e ordem do
pipeline); a web cobre pouco o comercio pequeno de Brasilia, entao a maioria dos rotulos e por tipo/OSM
(confianca B). Rotulos "2" exigem evidencia explicita. Revisao humana e medida de concordancia pendentes.
"""

import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AV = RAIZ / "docs" / "avaliacao"

# NOTA: place_id muda a cada curadoria (TRUNCATE RESTART IDENTITY); a chave ESTAVEL e `osm` (tipo/id).
# caso -> {"nucleo": criterio, "labels": {place_id: (grau, evid, conf, motivo)}}
R = {
 "TC-01": ("cafe calmo, acessivel (sem escadas), Asa Sul, manha, ate 5 km", {
  "1188": (1, "osm", "B", "wheelchair=yes; calma e horario sem fonte (web: nenhum resultado)"),
  "2723": (2, "web", "M", "wheelchair=yes, abre 09h; web: 'aconchegante', equipe simpatica (Sudoeste, 3,3 km)"),
  "1066": (0, "tipo", "B", "6,6 km: acima do raio de 5 km"),
  "970":  (1, "osm", "B", "wheelchair=yes, 07:30-21:00, wifi; calma sem fonte"),
  "903":  (0, "osm", "M", "endereco CLN 204 = Asa Norte, fora da regiao pedida"),
  "4186": (0, "osm", "M", "Guara, 6,2 km: fora do raio"),
  "868":  (0, "osm", "B", "6,7 km: fora do raio"),
  "1010": (0, "tipo", "B", "6,8 km: fora do raio"),
  "3097": (1, "osm", "B", "contraste; 07-20h; acessibilidade nao confirmada"),
  "1705": (1, "tipo", "B", "contraste; acessibilidade e calma sem fonte"),
  "1727": (1, "tipo", "B", "contraste; acessibilidade e calma sem fonte"),
  "2447": (1, "tipo", "B", "contraste; acessibilidade e calma sem fonte"),
  "2388": (1, "osm", "B", "contraste; CLS 108 = Asa Sul; acessibilidade nao confirmada"),
 }),
 "TC-02": ("lugar descontraido, final de tarde, grupo pequeno, jogos de tabuleiro/bate-papo, suco ou cerveja", {
  "578":  (1, "tipo", "B", "bar; jogos nao confirmados"),
  "3173": (1, "tipo", "B", "pub; jogos nao confirmados"),
  "775":  (1, "tipo", "B", "bar; jogos nao confirmados"),
  "1783": (0, "osm", "M", "OSM: Mo-Fr 08:15-17:30; fecha antes do 'final de tarde'"),
  "599":  (1, "tipo", "B", "bar de torcedores; jogos de tabuleiro nao confirmados"),
  "2454": (1, "tipo", "B", "cafe de rede; sem cerveja/jogos confirmados"),
  "1705": (1, "tipo", "B", "cafe; sem fonte"),
  "577":  (1, "tipo", "B", "bar e cafe; sem fonte"),
  "2938": (1, "tipo", "B", "contraste; bar; sem fonte"),
  "903":  (1, "tipo", "B", "contraste; cafe; sem fonte"),
  "846":  (2, "web", "M", "REFERENCIA: Carcassonne Pub (407 Norte) foca em jogos de tabuleiro (Correio Braziliense); OSM: Ter-Qui 18h-24h"),
 }),
 "TC-03": ("espaco silencioso p/ leitura em grupo e debate de livros (ficcao cientifica), livraria/centro cultural", {
  "3281": (2, "web", "M", "Biblioteca Nacional de Brasilia sedia 7 clubes de leitura mensais (Jornal de Brasilia/Correio); ficcao cientifica nao confirmada"),
  "1656": (1, "tipo", "B", "centro cultural; leitura em grupo sem fonte"),
  "3319": (0, "tipo", "B", "biblioteca infantil: publico e tema nao batem com debate adulto"),
  "1257": (0, "tipo", "B", "escola de cursos de arte"),
  "3453": (1, "osm", "B", "Caixa Cultural (Asa Sul, wheelchair=yes); leitura em grupo sem fonte"),
  "2648": (1, "osm", "B", "biblioteca legislativa; acesso e grupos sem fonte"),
  "2524": (1, "tipo", "B", "biblioteca especializada; acesso e grupos sem fonte"),
  "3283": (0, "tipo", "B", "centro de convencoes"),
  "3298": (1, "osm", "B", "contraste; espaco cultural com horario 'restricted'"),
  "3245": (1, "osm", "M", "contraste; biblioteca publica, OSM Seg-Sex 07:30-23:00; grupos sem fonte"),
 }),
 "TC-04": ("parque com pistas planas e sombra p/ caminhada leve em grupo de manha e conversa em banco", {
  "3471": (1, "tipo", "B", "parque urbano; pistas/sombra sem fonte"),
  "3843": (1, "tipo", "B", "praca; sem fonte"),
  "2875": (1, "osm", "B", "praca 24/7; sem fonte de pista/sombra"),
  "4029": (1, "osm", "B", "24/7; sem fonte"),
  "3596": (1, "tipo", "B", "area verde; sem fonte"),
  "3193": (0, "tipo", "B", "'Parquinho': playground infantil"),
  "3212": (1, "tipo", "B", "parque de quadra; sem fonte"),
  "3925": (1, "tipo", "B", "praca; sem fonte"),
  "3677": (1, "tipo", "B", "contraste; bosque urbano; sem fonte"),
  "3194": (0, "tipo", "B", "contraste; parquinho infantil"),
  "3228": (2, "web", "M", "REFERENCIA: Parque da Cidade; pistas de caminhada/ciclovia de 4, 6 e 10 km (web); OSM 24/7; nao veio do pipeline"),
 }),
 "TC-05": ("cafeteria com mesas externas e tomadas, onde se estuda/trabalha em grupo", {
  "1843": (2, "osm", "M", "OSM: outdoor_seating=yes e internet_access=yes; tomadas sem fonte"),
  "1783": (1, "osm", "M", "outdoor_seating=yes; Seg-Sex 08:15-17:30; tomadas/wifi sem fonte"),
  "970":  (1, "osm", "B", "wifi (OSM); mesas externas sem fonte"),
  "1188": (1, "tipo", "B", "sem fonte (web: nenhum resultado)"),
  "1657": (1, "osm", "B", "internet_access=wlan; mesas externas/tomadas sem fonte"),
  "1629": (1, "tipo", "B", "sem fonte"),
  "1554": (1, "tipo", "B", "sem fonte"),
  "2454": (1, "tipo", "B", "cafe de rede; tomadas sem fonte"),
  "1420": (1, "tipo", "B", "contraste; sem fonte"),
  "1187": (1, "tipo", "B", "contraste; sem fonte"),
 }),
 "TC-06": ("praca gastronomica/feirinha ao ar livre, musica ambiente moderada, sabado a noite", {
  "2668": (0, "tipo", "M", "praca de alimentacao de edificio comercial; nao e ao ar livre nem noite de sabado"),
  "1261": (0, "tipo", "B", "lanchonete"),
  "3314": (0, "osm", "M", "OSM: Ter-Qui 09-17h; fecha antes da noite e no sabado"),
  "2149": (0, "tipo", "B", "praca de alimentacao institucional"),
  "3313": (0, "osm", "M", "OSM: Ter-Qui 09-17h"),
  "7":    (1, "tipo", "B", "'Feirinha do anexo do Buriti': feira, mas horario/ar livre sem fonte"),
  "4329": (0, "tipo", "B", "11 km: acima do raio de 9 km"),
 }),
 "TC-07": ("restaurante vegetariano/vegano, Asa Norte, almoco, espaco arejado", {
  "1661": (2, "web", "M", "Apetit Natural: 100% vegano, buffet por peso, CLN 407 (Spinach/Correio); OSM sem horario"),
  "938":  (0, "osm", "M", "churrascaria"),
  "1660": (1, "tipo", "B", "sem fonte: cardapio nao confirmado"),
  "2089": (0, "osm", "M", "tem opcao vegana, mas OSM abre 17:00-00:00: nao serve almoco"),
  "969":  (1, "web", "M", "Greens: cozinha natural com buffet no almoco, nem sempre vegetariana (HappyCow); OSM vegan=yes"),
  "1800": (1, "web", "B", "Nutri Vida: saudavel, frutas; vegetariano nao confirmado"),
  "883":  (0, "osm", "M", "kebab"),
  "990":  (1, "tipo", "B", "sem fonte: cardapio nao confirmado"),
  "1940": (2, "web", "M", "contraste: Buriti Zen Vegano, OSM vegan=only; CLN 407 com almoco ate 15h (2020). NAO veio no top-8 do pipeline"),
  "964":  (1, "tipo", "B", "contraste; sem fonte"),
 }),
 "TC-08": ("cinema de rua/espaco de filmes alternativos com cafeteria integrada", {
  "1554": (0, "tipo", "B", "cafe sem cinema"), "1187": (0, "tipo", "B", "cafe sem cinema"),
  "1420": (0, "tipo", "B", "cafe sem cinema"), "1029": (0, "tipo", "B", "cafe sem cinema"),
  "2454": (0, "tipo", "B", "cafe sem cinema"), "900": (0, "tipo", "B", "cafe sem cinema"),
  "1783": (0, "tipo", "B", "cafe sem cinema"), "1088": (0, "tipo", "B", "cafe sem cinema"),
  "1705": (0, "tipo", "B", "contraste; cafe sem cinema"),
  "67":   (2, "web", "M", "contraste: CineCultura Liberty Mall, programacao alternativa premiada, reformado em 2025 com acessibilidade total (Jornal de Brasilia); cafeteria integrada NAO confirmada. Ficou fora do top-8 do pipeline"),
 }),
 "TC-09": ("atelie/centro comunitario publico p/ oficina de ceramica ou artesanato em grupo, a tarde", {
  "1656": (1, "tipo", "B", "centro cultural; oficinas sem fonte"),
  "1257": (1, "tipo", "B", "cursos de arte; publico/gratuidade sem fonte"),
  "1244": (1, "tipo", "B", "'Oficina de Arte'; comunitario/publico sem fonte"),
  "3453": (1, "tipo", "B", "centro cultural; oficinas sem fonte"),
  "2947": (1, "tipo", "B", "casa de cultura; oficinas sem fonte"),
  "3298": (1, "osm", "B", "espaco cultural; horario 'restricted'"),
  "3283": (0, "tipo", "B", "centro de convencoes"),
  "4522": (0, "osm", "M", "Clube do Choro: foco em musica; OSM Seg-Sab 18-22h, nao e a tarde"),
  "2156": (0, "tipo", "B", "contraste; espaco de eventos"),
  "3209": (1, "web", "M", "contraste: SESI Lab, museu de arte/ciencia; ja sediou oficinas e residencia artistica (Portal da Industria)"),
 }),
 "TC-10": ("parque/praca pet friendly com cercado para caes", {
  "3471": (1, "tipo", "B", "parque; area para caes sem fonte"),
  "2325": (0, "tipo", "B", "playground infantil"), "3194": (0, "tipo", "B", "parquinho infantil"),
  "4107": (0, "tipo", "B", "playground infantil"), "4375": (0, "tipo", "B", "playground infantil"),
  "4063": (0, "tipo", "B", "playground infantil"),
  "3843": (1, "tipo", "B", "praca; area para caes sem fonte"),
  "2875": (1, "osm", "B", "praca 24/7; area para caes sem fonte"),
  "3193": (0, "tipo", "B", "contraste; parquinho infantil"),
  "4029": (1, "osm", "B", "contraste; 24/7; sem fonte"),
  "3228": (2, "web", "M", "REFERENCIA: Parque da Cidade tem area para cachorros no Eixo Monumental Sul (quadras 901/906/910; lista de 2020). Nao veio do pipeline"),
 }),
 "TC-11": ("cha da tarde, ambiente discreto e pouco barulhento, mesas espacadas", {
  "1783": (1, "osm", "B", "Seg-Sex 08:15-17:30 cobre a tarde; discricao sem fonte"),
  "2454": (1, "tipo", "B", "cafe de rede; discricao sem fonte"),
  "1420": (1, "tipo", "B", "sem fonte"), "1554": (1, "tipo", "B", "sem fonte"),
  "1188": (1, "tipo", "B", "sem fonte"), "1705": (1, "tipo", "B", "sem fonte"),
  "1215": (1, "tipo", "B", "sem fonte"),
  "4332": (1, "web", "B", "'Casa de Cha': se for a da Praca dos Tres Poderes, e casa de cha, mas com altissima procura (reserva com meses de antecedencia), o que contradiz 'discreto'; identificacao OSM nao confirmada"),
  "1187": (1, "tipo", "B", "contraste; sem fonte"), "1088": (1, "tipo", "B", "contraste; sem fonte"),
 }),
 "TC-12": ("quadra publica ou parque com mesas de ping-pong/xadrez ao ar livre, gratuito", {
  "4376": (0, "tipo", "B", "quadra de tenis: nao sao mesas de jogos"),
  "170":  (1, "tipo", "B", "praca esportiva; mesas sem fonte"),
  "4374": (1, "tipo", "B", "quadra publica; sem mesas confirmadas"),
  "4208": (1, "tipo", "B", "quadra publica; sem mesas confirmadas"),
  "2507": (1, "tipo", "B", "quadra publica; sem mesas confirmadas"),
  "3291": (0, "tipo", "B", "clube de tenis: provavelmente pago/privado"),
  "3726": (0, "tipo", "B", "Torre de TV: mesas de jogos sem fonte"),
  "2184": (1, "tipo", "B", "quadra de frescobol; sem mesas"),
  "3309": (0, "tipo", "B", "contraste; clube privado"), "3308": (0, "tipo", "B", "contraste; clube privado"),
  "3471": (1, "tipo", "B", "AGENTE LLM: parque; mesas de jogos sem fonte"),
  "3764": (2, "web", "M", "REFERENCIA: Deck Sul tem mesas de jogos (dama, xadrez, pingue-pongue) e sombreiros (Diario do Poder, sem data). Nao veio do pipeline"),
 }),
 "TC-13": ("sushi/comida japonesa fresca, Asa Sul, mesas coletivas ou tatame", {
  "2176": (2, "web", "M", "Sushi San (107 Sul Bl C) tem tatame no piso superior (Correio Braziliense, sem data); duas entradas 'Sushi San' no OSM"),
  "730":  (2, "osm", "M", "Sushi San; OSM cuisine=sushi"),
  "656":  (2, "osm", "M", "OMA Japanese Experience; OSM cuisine=japanese;sushi"),
  "687":  (2, "web", "B", "Hana: rodizio japones (Correio Braziliense, 2026)"),
  "728":  (2, "web", "M", "Sumo: rodizio japones pioneiro, CLS 403/207 Asa Sul"),
  "3092": (2, "osm", "M", "Koji; OSM cuisine=japanese; addr:suburb=Asa Sul"),
  "1083": (0, "osm", "M", "cozinha indiana"),
  "2937": (1, "tipo", "B", "Yakiton: oriental/grelhados; sushi nao confirmado"),
  "1703": (2, "osm", "M", "contraste; Maxsushi; OSM cuisine=japanese;sushi"),
  "703":  (1, "tipo", "B", "contraste; Nippon; cozinha asiatica"),
 }),
 "TC-14": ("jardim florido/orquidario com banquinhos a sombra, manha de domingo, agua de coco", {
  "3811": (1, "tipo", "B", "area verde generica"), "3843": (1, "tipo", "B", "praca; sem fonte"),
  "3471": (1, "tipo", "B", "parque; sem fonte"), "3193": (0, "tipo", "B", "playground"),
  "3515": (1, "tipo", "B", "Praca das Fontes; sem fonte (web: nenhum resultado)"),
  "3596": (1, "tipo", "B", "area verde; sem fonte"),
  "1487": (1, "tipo", "B", "horta comunitaria: verde, mas nao jardim florido"),
  "1486": (1, "tipo", "B", "horta comunitaria: verde, mas nao jardim florido"),
  "3194": (0, "tipo", "B", "contraste; parquinho infantil"),
  "3247": (1, "tipo", "B", "contraste; praca; sem fonte"),
  "2810": (2, "web", "M", "REFERENCIA: Jardim Botanico de Brasilia: orquidario com ~3 mil orquideas, aberto Ter-Dom 9-17h, entrada gratuita (Catraca Livre/Agencia Brasilia); bancos a sombra sem fonte. 9,4 km, dentro do raio de 15 km. Nao veio do pipeline"),
 }),
 "TC-15": ("lanchonete/cafe cultural ate 22h, clima jovem, lanches rapidos e baratos", {
  "2547": (1, "tipo", "B", "sanduiches rapidos; horario e clima sem fonte"),
  "2454": (1, "tipo", "B", "cafe de rede; barato nao confirmado"),
  "1944": (1, "tipo", "B", "lanchonete; sem fonte"),
  "2546": (1, "tipo", "B", "pastelaria: lanche rapido/barato provavel; horario sem fonte"),
  "1945": (1, "tipo", "B", "sem fonte"), "1170": (1, "tipo", "B", "sanduiches rapidos; sem fonte"),
  "919":  (1, "tipo", "B", "sanduiches rapidos; sem fonte"), "1420": (1, "tipo", "B", "sem fonte"),
  "1422": (1, "tipo", "B", "contraste; sem fonte"), "1280": (1, "tipo", "B", "contraste; sem fonte"),
  "1489": (0, "osm", "M", "AGENTE LLM: Entre Eixos; OSM abre 09:00-17:00, nao atende 'aberto ate 22h'"),
  "1783": (0, "osm", "M", "AGENTE LLM: Melbourne Cafe; OSM Seg-Sex 08:15-17:30, nao atende 'aberto ate 22h'"),
 }),
}
SEEDS = {  # place_id -> (nome, categoria, lat, lon) lidos do banco
 "846": ("Carcassonne Pub", "pub", -15.7659, -47.8771, "node/2966823722"),
 "3228": ("Parque da Cidade Dona Sarah Kubitschek", "park", -15.8015, -47.9117, "way/25535698"),
 "3764": ("Deck Sul", "park", -15.8382, -47.9020, "way/495849346"),
 "2810": ("Jardim Botânico de Brasília", "garden", -15.8732, -47.8367, "node/12690162901"),
 "3471": ("Parque Ana Lídia", "park", -15.7937, -47.8959, "way/227022746"),
 "1489": ("Entre Eixos", "fast_food", -15.7899, -47.8803, "node/4716974234"),
 "1783": ("Melbourne Café & Co.", "cafe", -15.7902, -47.8847, "node/5416977721"),
}


def km(a, b):
    p = math.pi / 180
    h = math.sin((b[0]-a[0])*p/2)**2 + math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin((b[1]-a[1])*p/2)**2
    return 12742 * math.asin(math.sqrt(h))


def dcg(gs):
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gs))


def main():
    pool = {c["id"]: c for c in json.loads((AV / "pool_candidatos.json").read_text(encoding="utf-8"))}
    ficha = json.loads((AV / "pool_ficha_lugares.json").read_text(encoding="utf-8"))
    pedidos = {p["id"]: p for p in json.loads((AV / "pedidos_teste.json").read_text(encoding="utf-8"))}
    saida, metr = {}, []
    for tid, (nucleo, labels) in R.items():
        cands = {i["place_id"]: i for i in pool[tid]["candidatos"]}
        ponto = tuple(pool[tid]["local_resolvido"][:2])
        itens = []
        for pid, (g, ev, conf, motivo) in labels.items():
            if pid in cands:
                c = cands[pid]; nome = ficha[pid]["nome"]; cat = ficha[pid]["categoria"]; osm = ficha[pid]["osm"]; origem = c["origem"]; dist = c["distancia_km"]
                posicao = [x["place_id"] for x in pool[tid]["candidatos"] if x["origem"] == "pipeline"].index(pid) + 1 if origem == "pipeline" else None
            else:
                nome, cat, la, lo, osm = SEEDS[pid]; origem = "agente_llm" if pid in ("3471", "1489", "1783") else "referencia"; dist = round(km(ponto, (la, lo)), 2); posicao = None
            itens.append({"place_id": pid, "osm": osm, "nome": nome, "categoria": cat, "origem": origem, "posicao_pipeline": posicao,
                          "distancia_km": dist, "grau": g, "evidencia": ev, "confianca": conf, "motivo": motivo})
        faltando = set(cands) - set(labels)
        assert not faltando, (tid, faltando)
        pipe = sorted([i for i in itens if i["origem"] == "pipeline"], key=lambda i: i["posicao_pipeline"])
        top3 = [i["grau"] for i in pipe[:3]]
        ideal = sorted([i["grau"] for i in itens], reverse=True)[:3]
        saida[tid] = {"acao_esperada": "recomendar", "nucleo": nucleo, "query": pedidos[tid]["query"], "labels": itens}
        metr.append({"id": tid, "p3_pipeline": round(sum(g >= 1 for g in top3) / 3, 2), "ndcg3_pipeline": round(dcg(top3) / dcg(ideal), 2) if dcg(ideal) else None,
                     "top3_graus": top3, "n_grau2": sum(i["grau"] == 2 for i in itens), "n_grau2_fora_do_pipeline": sum(i["grau"] == 2 and i["origem"] != "pipeline" for i in itens),
                     "max_p3": round(min(3, sum(i["grau"] >= 1 for i in itens)) / 3, 2)})
    saida["TC-16"] = {"acao_esperada": "clarificar", "nucleo": "pedido ambiguo: a resposta correta e perguntar; candidatos nao rotulados", "labels": []}
    saida["TC-17"] = {"acao_esperada": "abster", "nucleo": "criterio impossivel (patinacao no gelo + 03:30)", "labels": []}
    saida["TC-18"] = {"acao_esperada": "abster", "nucleo": "fora de escopo (frete)", "labels": []}
    (AV / "rotulos_osm_v1.json").write_text(json.dumps({"anotador": "Claude (unico, nao cego)", "versao": "v1.1 (v1 + 3 lugares entregues pelo agente LLM)", "escala": "0/1/2", "casos": saida, "baseline_pipeline": metr}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [m for m in metr if m["ndcg3_pipeline"] is not None]
    print(f"{len(metr)} casos rotulados; {sum(len(v['labels']) for v in saida.values())} rotulos")
    print(f"baseline do pipeline atual: P@3 medio={sum(m['p3_pipeline'] for m in metr)/len(metr):.2f} | nDCG@3 medio={sum(m['ndcg3_pipeline'] for m in ok)/len(ok):.2f}")
    for m in metr:
        print(f"  {m['id']} P@3={m['p3_pipeline']:.2f} (max {m['max_p3']:.2f}) nDCG@3={m['ndcg3_pipeline']} top3={m['top3_graus']} grau2={m['n_grau2']} (fora do pipeline: {m['n_grau2_fora_do_pipeline']})")


if __name__ == "__main__":
    main()
