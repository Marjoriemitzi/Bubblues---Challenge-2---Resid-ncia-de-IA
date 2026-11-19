# Gabarito OSM v1 (relevância graduada sobre lugares reais)

**Escala:** 2 = atende o núcleo do pedido; 1 = alternativa aceitável/parcial ou atributo central não confirmado; 0 = não atende (tipo errado ou violação com evidência: horário no OSM, bairro explícito, distância > raio).

**Evidência:** `web` pesquisa na internet · `osm` tags do banco · `tipo` só categoria/nome · `ref` conhecimento do anotador. **Confiança:** A alta · M média · B baixa.

## Limitações (leia antes de usar)

- **Anotador único e IA (Claude)**; não é cego: o anotador viu os scores e a ordem do pipeline. Rótulo gerado por IA não é verdade de referência. Falta revisão humana e medida de concordância (kappa).
- **A web cobre pouco o comércio pequeno de Brasília** (ex.: 'Tomilla Café' e 'Café das Letras' não retornaram nada). Por isso a maioria dos rótulos vem de tipo/OSM (confiança B). **Só 2 com evidência explícita.**
- **'1' inclui 'não confirmado'** (convenção do gabarito v2). Isso **infla P@3** e faz o nDCG@3 virar 1,0 sem informação onde nenhum candidato tem grau 2 (TC-09, TC-11, TC-15). Use o nDCG com cautela nesses casos.
- **Pool enviesado pelo próprio pipeline** (top-8 + 5 de contraste). Foram acrescentados 4 candidatos de referência achados na pesquisa (`origem=referencia`); podem existir outros melhores que não foram vistos.
- Ruído: o OSM do DF não tem `noise_level`; nenhum rótulo de calma tem fonte além de web/nome.

## Baseline do pipeline atual (top-3 por ordem do pipeline, Retrieval determinístico)

| Caso | P@3 | máx. P@3 | nDCG@3 | graus do top-3 | nº de grau 2 | grau 2 fora do pipeline |
|---|---:|---:|---:|---|---:|---:|
| TC-01 | 0.67 | 1.00 | 0.7 | [1, 2, 0] | 1 | 0 |
| TC-02 | 1.00 | 1.00 | 0.52 | [1, 1, 1] | 1 | 1 |
| TC-03 | 0.67 | 1.00 | 0.88 | [2, 1, 0] | 1 | 0 |
| TC-04 | 1.00 | 1.00 | 0.52 | [1, 1, 1] | 1 | 1 |
| TC-05 | 1.00 | 1.00 | 1.0 | [2, 1, 1] | 1 | 0 |
| TC-06 | 0.00 | 0.33 | 0.0 | [0, 0, 0] | 0 | 0 |
| TC-07 | 0.67 | 1.00 | 0.65 | [2, 0, 1] | 2 | 1 |
| TC-08 | 0.00 | 0.33 | 0.0 | [0, 0, 0] | 1 | 1 |
| TC-09 | 1.00 | 1.00 | 1.0 | [1, 1, 1] | 0 | 0 |
| TC-10 | 0.33 | 1.00 | 0.24 | [1, 0, 0] | 1 | 1 |
| TC-11 | 1.00 | 1.00 | 1.0 | [1, 1, 1] | 0 | 0 |
| TC-12 | 0.67 | 1.00 | 0.27 | [0, 1, 1] | 1 | 1 |
| TC-13 | 1.00 | 1.00 | 1.0 | [2, 2, 2] | 7 | 1 |
| TC-14 | 1.00 | 1.00 | 0.52 | [1, 1, 1] | 1 | 1 |
| TC-15 | 1.00 | 1.00 | 1.0 | [1, 1, 1] | 0 | 0 |

**Média:** P@3 = 0.73; nDCG@3 = 0.62 (15 casos a recomendar).

## TC-01 (recomendar)
> Gostaria de um café calmo e tranquilo na Asa Sul, com boa acessibilidade para caminhar sem escadas, para conversar com pessoas da minha faixa etária pela manhã.
**Núcleo:** cafe calmo, acessivel (sem escadas), Asa Sul, manha, ate 5 km

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Saboretto Cafés Especiais (`2723`) | cafe | pipeline #2 | 3.32 | web/M | wheelchair=yes, abre 09h; web: 'aconchegante', equipe simpatica (Sudoeste, 3,3 km) |
| **1** | Tomilla Café (`1188`) | cafe | pipeline #1 | 3.78 | osm/B | wheelchair=yes; calma e horario sem fonte (web: nenhum resultado) |
| **1** | Caramella (`970`) | cafe | pipeline #4 | 4.29 | osm/B | wheelchair=yes, 07:30-21:00, wifi; calma sem fonte |
| **1** | The Coffee (`3097`) | cafe | contraste | 0.32 | osm/B | contraste; 07-20h; acessibilidade nao confirmada |
| **1** | Nosso Quadrado (`1705`) | cafe | contraste | 1.72 | tipo/B | contraste; acessibilidade e calma sem fonte |
| **1** | Uai Bezinha! (`1727`) | cafe | contraste | 1.33 | tipo/B | contraste; acessibilidade e calma sem fonte |
| **1** | Café da Mata (`2447`) | cafe | contraste | 1.32 | tipo/B | contraste; acessibilidade e calma sem fonte |
| **1** | Lugano (`2388`) | cafe | contraste | 0.37 | osm/B | contraste; CLS 108 = Asa Sul; acessibilidade nao confirmada |
| **0** | Café das Letras (`1066`) | cafe | pipeline #3 | 6.59 | tipo/B | 6,6 km: acima do raio de 5 km |
| **0** | Candy House (`903`) | cafe | pipeline #5 | 4.99 | osm/M | endereco CLN 204 = Asa Norte, fora da regiao pedida |
| **0** | Casa de Biscoitos Mineiros (`4186`) | cafe | pipeline #6 | 6.25 | osm/M | Guara, 6,2 km: fora do raio |
| **0** | Amor à Torta (`868`) | cafe | pipeline #7 | 6.73 | osm/B | 6,7 km: fora do raio |
| **0** | D'Vilella (`1010`) | cafe | pipeline #8 | 6.78 | tipo/B | 6,8 km: fora do raio |

## TC-02 (recomendar)
> Procuro um lugar descontraído no final de tarde para encontrar um grupo pequeno para jogar jogos de tabuleiro ou bater papo tomando um suco ou cerveja artesanal.
**Núcleo:** lugar descontraido, final de tarde, grupo pequeno, jogos de tabuleiro/bate-papo, suco ou cerveja

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Carcassonne Pub (`846`) | pub | referencia | 3.17 | web/M | REFERENCIA: Carcassonne Pub (407 Norte) foca em jogos de tabuleiro (Correio Braziliense); OSM: Ter-Qui 18h-24h |
| **1** | Beer Selection (`578`) | bar | pipeline #1 | 1.11 | tipo/B | bar; jogos nao confirmados |
| **1** | Conic (`3173`) | pub | pipeline #2 | 0.32 | tipo/B | pub; jogos nao confirmados |
| **1** | Barulho (`775`) | bar | pipeline #3 | 1.97 | tipo/B | bar; jogos nao confirmados |
| **1** | Só Drinks Bar dos Botafoguenses (`599`) | bar | pipeline #5 | 1.75 | tipo/B | bar de torcedores; jogos de tabuleiro nao confirmados |
| **1** | Starbucks (`2454`) | cafe | pipeline #6 | 0.32 | tipo/B | cafe de rede; sem cerveja/jogos confirmados |
| **1** | Nosso Quadrado (`1705`) | cafe | pipeline #7 | 1.49 | tipo/B | cafe; sem fonte |
| **1** | Bar e Café do Brasil (`577`) | bar | pipeline #8 | 1.24 | tipo/B | bar e cafe; sem fonte |
| **1** | Biricutico (`2938`) | bar | contraste | 2.61 | tipo/B | contraste; bar; sem fonte |
| **1** | Candy House (`903`) | cafe | contraste | 1.92 | tipo/B | contraste; cafe; sem fonte |
| **0** | Melbourne Café & Co. (`1783`) | cafe | pipeline #4 | 0.45 | osm/M | OSM: Mo-Fr 08:15-17:30; fecha antes do 'final de tarde' |

## TC-03 (recomendar)
> Um espaço silencioso e aconchegante para leitura em grupo e debate sobre livros de ficção científica, de preferência integrado a uma livraria ou centro cultural.
**Núcleo:** espaco silencioso p/ leitura em grupo e debate de livros (ficcao cientifica), livraria/centro cultural

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Biblioteca Nacional de Brasília Leonel de Moura Brizola (`3281`) | library | pipeline #1 | 0.42 | web/M | Biblioteca Nacional de Brasilia sedia 7 clubes de leitura mensais (Jornal de Brasilia/Correio); ficcao cientifica nao confirmada |
| **1** | Espaço Cultural Canteiro Central (`1656`) | arts_centre | pipeline #2 | 0.67 | tipo/B | centro cultural; leitura em grupo sem fonte |
| **1** | Caixa Cultural (`3453`) | arts_centre | pipeline #5 | 1.12 | osm/B | Caixa Cultural (Asa Sul, wheelchair=yes); leitura em grupo sem fonte |
| **1** | Biblioteca Pedro Aleixo (`2648`) | library | pipeline #6 | 2.13 | osm/B | biblioteca legislativa; acesso e grupos sem fonte |
| **1** | Biblioteca do Senado Federal (`2524`) | library | pipeline #7 | 2.07 | tipo/B | biblioteca especializada; acesso e grupos sem fonte |
| **1** | Espaço Cultural Renato Guerreiro - Anatel (`3298`) | arts_centre | contraste | 1.25 | osm/B | contraste; espaco cultural com horario 'restricted' |
| **1** | Biblioteca Demonstrativa de Brasília (`3245`) | library | contraste | 2.82 | osm/M | contraste; biblioteca publica, OSM Seg-Sex 07:30-23:00; grupos sem fonte |
| **0** | Biblioteca Infantil (`3319`) | library | pipeline #3 | 2.02 | tipo/B | biblioteca infantil: publico e tema nao batem com debate adulto |
| **0** | Cursos de Artes (`1257`) | arts_centre | pipeline #4 | 1.18 | tipo/B | escola de cursos de arte |
| **0** | Centro de Convenções Ulysses Guimarães (`3283`) | arts_centre | pipeline #8 | 1.98 | tipo/B | centro de convencoes |

## TC-04 (recomendar)
> Parque aberto com pistas planas e sombras de árvores para uma caminhada leve em grupo no início da manhã, seguido de conversa em banco de praça.
**Núcleo:** parque com pistas planas e sombra p/ caminhada leve em grupo de manha e conversa em banco

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Parque da Cidade Dona Sarah Kubitschek (`3228`) | park | referencia | 3.21 | web/M | REFERENCIA: Parque da Cidade; pistas de caminhada/ciclovia de 4, 6 e 10 km (web); OSM 24/7; nao veio do pipeline |
| **1** | Parque Ana Lídia (`3471`) | park | pipeline #1 | 1.41 | tipo/B | parque urbano; pistas/sombra sem fonte |
| **1** | Praça Galeria (`3843`) | park | pipeline #2 | 0.67 | tipo/B | praca; sem fonte |
| **1** | Praça dos artistas (`2875`) | park | pipeline #3 | 0.9 | osm/B | praca 24/7; sem fonte de pista/sombra |
| **1** | Ponto de Convivência (`4029`) | park | pipeline #4 | 3.23 | osm/B | 24/7; sem fonte |
| **1** | Galeria dos Estados (`3596`) | park | pipeline #5 | 0.6 | tipo/B | area verde; sem fonte |
| **1** | Parque da 202/203 Sul (`3212`) | park | pipeline #7 | 1.57 | tipo/B | parque de quadra; sem fonte |
| **1** | Praça dos Cogumelos (`3925`) | park | pipeline #8 | 3.36 | tipo/B | praca; sem fonte |
| **1** | Bosque dos Constituintes (`3677`) | park | contraste | 2.46 | tipo/B | contraste; bosque urbano; sem fonte |
| **0** | Parquinho (`3193`) | park | pipeline #6 | 2.06 | tipo/B | 'Parquinho': playground infantil |
| **0** | Parquinho Infantil (`3194`) | park | contraste | 2.12 | tipo/B | contraste; parquinho infantil |

## TC-05 (recomendar)
> Cafeteria com mesinhas externas e tomadas, onde seja comum ver pessoas estudando ou trabalhando em grupo com laptops.
**Núcleo:** cafeteria com mesas externas e tomadas, onde se estuda/trabalha em grupo

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Quanto (`1843`) | cafe | pipeline #1 | 1.81 | osm/M | OSM: outdoor_seating=yes e internet_access=yes; tomadas sem fonte |
| **1** | Melbourne Café & Co. (`1783`) | cafe | pipeline #2 | 0.45 | osm/M | outdoor_seating=yes; Seg-Sex 08:15-17:30; tomadas/wifi sem fonte |
| **1** | Caramella (`970`) | cafe | pipeline #3 | 1.51 | osm/B | wifi (OSM); mesas externas sem fonte |
| **1** | Tomilla Café (`1188`) | cafe | pipeline #4 | 0.75 | tipo/B | sem fonte (web: nenhum resultado) |
| **1** | Café Civitá (`1657`) | cafe | pipeline #5 | 1.1 | osm/B | internet_access=wlan; mesas externas/tomadas sem fonte |
| **1** | Oficina Café (`1629`) | cafe | pipeline #6 | 1.6 | tipo/B | sem fonte |
| **1** | Gaudi Café (`1554`) | cafe | pipeline #7 | 0.36 | tipo/B | sem fonte |
| **1** | Starbucks (`2454`) | cafe | pipeline #8 | 0.32 | tipo/B | cafe de rede; tomadas sem fonte |
| **1** | Grande Café (`1420`) | cafe | contraste | 0.76 | tipo/B | contraste; sem fonte |
| **1** | Art Café (`1187`) | cafe | contraste | 0.68 | tipo/B | contraste; sem fonte |

## TC-06 (recomendar)
> Gostaria de uma praça gastronômica ou feirinha ao ar livre com música ambiente moderada no sábado à noite para interagir com novas pessoas.
**Núcleo:** praca gastronomica/feirinha ao ar livre, musica ambiente moderada, sabado a noite

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **1** | Feirinha do anexo do Buriti (`7`) | food_court | pipeline #6 | 3.02 | tipo/B | 'Feirinha do anexo do Buriti': feira, mas horario/ar livre sem fonte |
| **0** | Edifício Financial Center Park (`2668`) | food_court | pipeline #1 | 0.52 | tipo/M | praca de alimentacao de edificio comercial; nao e ao ar livre nem noite de sabado |
| **0** | Lanchonete Pimenta de Cheiro (`1261`) | food_court | pipeline #2 | 0.93 | tipo/B | lanchonete |
| **0** | Bloco Q (`3314`) | food_court | pipeline #3 | 1.3 | osm/M | OSM: Ter-Qui 09-17h; fecha antes da noite e no sabado |
| **0** | Espaço do Servidor (`2149`) | food_court | pipeline #4 | 2.32 | tipo/B | praca de alimentacao institucional |
| **0** | Bloco R (`3313`) | food_court | pipeline #5 | 1.3 | osm/M | OSM: Ter-Qui 09-17h |
| **0** | PRAÇA DE ALIMENTAÇÃO (`4329`) | food_court | pipeline #7 | 11.02 | tipo/B | 11 km: acima do raio de 9 km |

## TC-07 (recomendar)
> Restaurante com culinária saudável e vegetariana/vegana na Asa Norte, com espaço arejado e cardápio vegetal para um almoço de socialização.
**Núcleo:** restaurante vegetariano/vegano, Asa Norte, almoco, espaco arejado

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Apetit Natural (`1661`) | restaurant | pipeline #1 | 0.73 | web/M | Apetit Natural: 100% vegano, buffet por peso, CLN 407 (Spinach/Correio); OSM sem horario |
| **2** | Buriti Zen Vegano (`1940`) | restaurant | contraste | 0.77 | web/M | contraste: Buriti Zen Vegano, OSM vegan=only; CLN 407 com almoco ate 15h (2020). NAO veio no top-8 do pipeline |
| **1** | A Tribo (`1660`) | restaurant | pipeline #3 | 0.95 | tipo/B | sem fonte: cardapio nao confirmado |
| **1** | Greens (`969`) | restaurant | pipeline #5 | 2.0 | web/M | Greens: cozinha natural com buffet no almoco, nem sempre vegetariana (HappyCow); OSM vegan=yes |
| **1** | Nutri Vida (`1800`) | restaurant | pipeline #6 | 2.06 | web/B | Nutri Vida: saudavel, frutas; vegetariano nao confirmado |
| **1** | Maori (`990`) | restaurant | pipeline #8 | 0.65 | tipo/B | sem fonte: cardapio nao confirmado |
| **1** | Saborear (`964`) | restaurant | contraste | 0.63 | tipo/B | contraste; sem fonte |
| **0** | Churrasgril (`938`) | restaurant | pipeline #2 | 0.83 | osm/M | churrascaria |
| **0** | Cozinha do Salim (`2089`) | restaurant | pipeline #4 | 0.39 | osm/M | tem opcao vegana, mas OSM abre 17:00-00:00: nao serve almoco |
| **0** | Kikebab (`883`) | restaurant | pipeline #7 | 0.62 | osm/M | kebab |

## TC-08 (recomendar)
> Cinema de rua ou espaço exibidor de filmes alternativos com cafeteria integrada para debate pós-sessão com os outros participantes.
**Núcleo:** cinema de rua/espaco de filmes alternativos com cafeteria integrada

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | CineCultura Liberty Mall (`67`) | cinema | contraste | 0.83 | web/M | contraste: CineCultura Liberty Mall, programacao alternativa premiada, reformado em 2025 com acessibilidade total (Jornal de Brasilia); cafeteria integrada NAO confirmada. Ficou fora do top-8 do pipeline |
| **0** | Gaudi Café (`1554`) | cafe | pipeline #1 | 0.36 | tipo/B | cafe sem cinema |
| **0** | Art Café (`1187`) | cafe | pipeline #2 | 0.68 | tipo/B | cafe sem cinema |
| **0** | Grande Café (`1420`) | cafe | pipeline #3 | 0.76 | tipo/B | cafe sem cinema |
| **0** | Café com Café (`1029`) | cafe | pipeline #4 | 1.48 | tipo/B | cafe sem cinema |
| **0** | Starbucks (`2454`) | cafe | pipeline #5 | 0.32 | tipo/B | cafe sem cinema |
| **0** | Cafezinho Express (`900`) | cafe | pipeline #6 | 0.86 | tipo/B | cafe sem cinema |
| **0** | Melbourne Café & Co. (`1783`) | cafe | pipeline #7 | 0.45 | tipo/B | cafe sem cinema |
| **0** | Café do Ponto (`1088`) | cafe | pipeline #8 | 1.2 | tipo/B | cafe sem cinema |
| **0** | Nosso Quadrado (`1705`) | cafe | contraste | 1.49 | tipo/B | contraste; cafe sem cinema |

## TC-09 (recomendar)
> Ateliê comunitário ou centro de convivência público para oficina de cerâmica ou artesanato em grupo na parte da tarde.
**Núcleo:** atelie/centro comunitario publico p/ oficina de ceramica ou artesanato em grupo, a tarde

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **1** | Espaço Cultural Canteiro Central (`1656`) | arts_centre | pipeline #1 | 0.67 | tipo/B | centro cultural; oficinas sem fonte |
| **1** | Cursos de Artes (`1257`) | arts_centre | pipeline #2 | 1.18 | tipo/B | cursos de arte; publico/gratuidade sem fonte |
| **1** | Oficina de Arte (`1244`) | arts_centre | pipeline #3 | 1.87 | tipo/B | 'Oficina de Arte'; comunitario/publico sem fonte |
| **1** | Caixa Cultural (`3453`) | arts_centre | pipeline #4 | 1.12 | tipo/B | centro cultural; oficinas sem fonte |
| **1** | Casa da Cultura Brasília (`2947`) | arts_centre | pipeline #5 | 1.75 | tipo/B | casa de cultura; oficinas sem fonte |
| **1** | Espaço Cultural Renato Guerreiro - Anatel (`3298`) | arts_centre | pipeline #6 | 1.25 | osm/B | espaco cultural; horario 'restricted' |
| **1** | SESI Lab (`3209`) | arts_centre | contraste | 0.27 | web/M | contraste: SESI Lab, museu de arte/ciencia; ja sediou oficinas e residencia artistica (Portal da Industria) |
| **0** | Centro de Convenções Ulysses Guimarães (`3283`) | arts_centre | pipeline #7 | 1.98 | tipo/B | centro de convencoes |
| **0** | Clube do Choro de Brasília (`4522`) | arts_centre | pipeline #8 | 1.85 | osm/M | Clube do Choro: foco em musica; OSM Seg-Sab 18-22h, nao e a tarde |
| **0** | Espaco Brasilia Eventos (`2156`) | arts_centre | contraste | 2.02 | tipo/B | contraste; espaco de eventos |

## TC-10 (recomendar)
> Parque ou praça pet friendly com cercado para cachorros, onde tutores costumam se reunir para deixar os pets brincarem e socializarem.
**Núcleo:** parque/praca pet friendly com cercado para caes

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Parque da Cidade Dona Sarah Kubitschek (`3228`) | park | referencia | 3.21 | web/M | REFERENCIA: Parque da Cidade tem area para cachorros no Eixo Monumental Sul (quadras 901/906/910; lista de 2020). Nao veio do pipeline |
| **1** | Parque Ana Lídia (`3471`) | park | pipeline #1 | 1.41 | tipo/B | parque; area para caes sem fonte |
| **1** | Praça Galeria (`3843`) | park | pipeline #5 | 0.67 | tipo/B | praca; area para caes sem fonte |
| **1** | Praça dos artistas (`2875`) | park | pipeline #6 | 0.9 | osm/B | praca 24/7; area para caes sem fonte |
| **1** | Ponto de Convivência (`4029`) | park | contraste | 3.23 | osm/B | contraste; 24/7; sem fonte |
| **0** | Parquinho de madeira (`2325`) | playground | pipeline #2 | 1.75 | tipo/B | playground infantil |
| **0** | Parquinho Infantil (`3194`) | park | pipeline #3 | 2.12 | tipo/B | parquinho infantil |
| **0** | Parquinho (`4107`) | playground | pipeline #4 | 1.44 | tipo/B | playground infantil |
| **0** | Parquinho (`4375`) | playground | pipeline #7 | 1.73 | tipo/B | playground infantil |
| **0** | Parquinho Infantil do Bloco G da 104 Sul (`4063`) | park | pipeline #8 | 2.06 | tipo/B | playground infantil |
| **0** | Parquinho (`3193`) | park | contraste | 2.06 | tipo/B | contraste; parquinho infantil |

## TC-11 (recomendar)
> Quero um chá da tarde em ambiente muito discreto e pouco barulhento, com mesas espaçadas para conversar sem me sentir vigiado.
**Núcleo:** cha da tarde, ambiente discreto e pouco barulhento, mesas espacadas

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **1** | Melbourne Café & Co. (`1783`) | cafe | pipeline #1 | 0.45 | osm/B | Seg-Sex 08:15-17:30 cobre a tarde; discricao sem fonte |
| **1** | Starbucks (`2454`) | cafe | pipeline #2 | 0.32 | tipo/B | cafe de rede; discricao sem fonte |
| **1** | Grande Café (`1420`) | cafe | pipeline #3 | 0.76 | tipo/B | sem fonte |
| **1** | Gaudi Café (`1554`) | cafe | pipeline #4 | 0.36 | tipo/B | sem fonte |
| **1** | Tomilla Café (`1188`) | cafe | pipeline #5 | 0.75 | tipo/B | sem fonte |
| **1** | Nosso Quadrado (`1705`) | cafe | pipeline #6 | 1.49 | tipo/B | sem fonte |
| **1** | Chateau Brasil (`1215`) | cafe | pipeline #7 | 0.48 | tipo/B | sem fonte |
| **1** | Casa de Chá (`4332`) | cafe | pipeline #8 | 2.48 | web/B | 'Casa de Cha': se for a da Praca dos Tres Poderes, e casa de cha, mas com altissima procura (reserva com meses de antecedencia), o que contradiz 'discreto'; identificacao OSM nao confirmada |
| **1** | Art Café (`1187`) | cafe | contraste | 0.68 | tipo/B | contraste; sem fonte |
| **1** | Café do Ponto (`1088`) | cafe | contraste | 1.2 | tipo/B | contraste; sem fonte |

## TC-12 (recomendar)
> Quadra pública ou parque com mesas de ping-pong ou xadrez ao ar livre para encontrar parceiros de partida recreativa sem custo.
**Núcleo:** quadra publica ou parque com mesas de ping-pong/xadrez ao ar livre, gratuito

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Deck Sul (`3764`) | park | referencia | 5.34 | web/M | REFERENCIA: Deck Sul tem mesas de jogos (dama, xadrez, pingue-pongue) e sombreiros (Diario do Poder, sem data). Nao veio do pipeline |
| **1** | Praça das bicicletas (`170`) | pitch | pipeline #2 | 0.48 | tipo/B | praca esportiva; mesas sem fonte |
| **1** | Quadra poliesportiva (`4374`) | pitch | pipeline #3 | 1.72 | tipo/B | quadra publica; sem mesas confirmadas |
| **1** | Quadra de esportes (`4208`) | pitch | pipeline #4 | 1.73 | tipo/B | quadra publica; sem mesas confirmadas |
| **1** | Quadra esportiva (`2507`) | pitch | pipeline #5 | 2.04 | tipo/B | quadra publica; sem mesas confirmadas |
| **1** | Quadra Frescobol (`2184`) | pitch | pipeline #8 | 1.66 | tipo/B | quadra de frescobol; sem mesas |
| **0** | Quadra de tênis (`4376`) | pitch | pipeline #1 | 1.46 | tipo/B | quadra de tenis: nao sao mesas de jogos |
| **0** | Amigos do Tênis (`3291`) | pitch | pipeline #6 | 3.3 | tipo/B | clube de tenis: provavelmente pago/privado |
| **0** | Torre de TV (`3726`) | park | pipeline #7 | 1.0 | tipo/B | Torre de TV: mesas de jogos sem fonte |
| **0** | NIPPO Club (`3309`) | pitch | contraste | 4.22 | tipo/B | contraste; clube privado |
| **0** | NIPPO Club (`3308`) | pitch | contraste | 4.24 | tipo/B | contraste; clube privado |

## TC-13 (recomendar)
> Quero comer sushi e comida japonesa fresca num restaurante agradável na Asa Sul com mesas coletivas ou tatames aconchegantes.
**Núcleo:** sushi/comida japonesa fresca, Asa Sul, mesas coletivas ou tatame

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Sushi San (`2176`) | restaurant | pipeline #1 | 0.66 | web/M | Sushi San (107 Sul Bl C) tem tatame no piso superior (Correio Braziliense, sem data); duas entradas 'Sushi San' no OSM |
| **2** | Sushi San (`730`) | restaurant | pipeline #2 | 1.57 | osm/M | Sushi San; OSM cuisine=sushi |
| **2** | OMA Japanese Experience (`656`) | restaurant | pipeline #3 | 1.34 | osm/M | OMA Japanese Experience; OSM cuisine=japanese;sushi |
| **2** | Hana (`687`) | restaurant | pipeline #4 | 0.66 | web/B | Hana: rodizio japones (Correio Braziliense, 2026) |
| **2** | Sumo (`728`) | restaurant | pipeline #5 | 1.35 | web/M | Sumo: rodizio japones pioneiro, CLS 403/207 Asa Sul |
| **2** | Koji (`3092`) | restaurant | pipeline #6 | 0.56 | osm/M | Koji; OSM cuisine=japanese; addr:suburb=Asa Sul |
| **2** | Maxsushi (`1703`) | restaurant | contraste | 1.7 | osm/M | contraste; Maxsushi; OSM cuisine=japanese;sushi |
| **1** | Yakiton (`2937`) | restaurant | pipeline #8 | 0.87 | tipo/B | Yakiton: oriental/grelhados; sushi nao confirmado |
| **1** | Nippon (`703`) | restaurant | contraste | 2.0 | tipo/B | contraste; Nippon; cozinha asiatica |
| **0** | Ashram Zen Lounge (`1083`) | restaurant | pipeline #7 | 0.67 | osm/M | cozinha indiana |

## TC-14 (recomendar)
> Espaço com jardim florido ou orquidário com banquinhos à sombra para conversar e tomar uma água de coco na manhã de domingo.
**Núcleo:** jardim florido/orquidario com banquinhos a sombra, manha de domingo, agua de coco

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **2** | Jardim Botânico de Brasília (`2810`) | garden | referencia | 10.1 | web/M | REFERENCIA: Jardim Botanico de Brasilia: orquidario com ~3 mil orquideas, aberto Ter-Dom 9-17h, entrada gratuita (Catraca Livre/Agencia Brasilia); bancos a sombra sem fonte. 9,4 km, dentro do raio de 15 km. Nao veio do pipeline |
| **1** | Área verde (`3811`) | garden | pipeline #1 | 0.76 | tipo/B | area verde generica |
| **1** | Praça Galeria (`3843`) | park | pipeline #2 | 0.67 | tipo/B | praca; sem fonte |
| **1** | Parque Ana Lídia (`3471`) | park | pipeline #3 | 1.41 | tipo/B | parque; sem fonte |
| **1** | Praça das Fontes (`3515`) | garden | pipeline #5 | 3.6 | tipo/B | Praca das Fontes; sem fonte (web: nenhum resultado) |
| **1** | Galeria dos Estados (`3596`) | park | pipeline #6 | 0.6 | tipo/B | area verde; sem fonte |
| **1** | Horta Comunitária (`1487`) | garden | pipeline #7 | 2.94 | tipo/B | horta comunitaria: verde, mas nao jardim florido |
| **1** | Horta Comunitária (`1486`) | garden | pipeline #8 | 2.96 | tipo/B | horta comunitaria: verde, mas nao jardim florido |
| **1** | Praça Índio Pataxó Galdino Jesus dos Santos (`3247`) | park | contraste | 1.9 | tipo/B | contraste; praca; sem fonte |
| **0** | Parquinho (`3193`) | park | pipeline #4 | 2.06 | tipo/B | playground |
| **0** | Parquinho Infantil (`3194`) | park | contraste | 2.12 | tipo/B | contraste; parquinho infantil |

## TC-15 (recomendar)
> Lanchonete ou café cultural perto da universidade aberto até às 22h com clima jovem e opções de lanches rápidos e baratos.
**Núcleo:** lanchonete/cafe cultural ate 22h, clima jovem, lanches rapidos e baratos

| Grau | Lugar | Cat. | Origem (pos.) | km | Evid./Conf. | Motivo |
|:-:|---|---|---|---:|:-:|---|
| **1** | Subway (`2547`) | fast_food | pipeline #1 | 0.08 | tipo/B | sanduiches rapidos; horario e clima sem fonte |
| **1** | Starbucks (`2454`) | cafe | pipeline #2 | 0.32 | tipo/B | cafe de rede; barato nao confirmado |
| **1** | Sabor do Café (`1944`) | fast_food | pipeline #3 | 0.71 | tipo/B | lanchonete; sem fonte |
| **1** | Pastelaria Viçosa (`2546`) | fast_food | pipeline #4 | 0.09 | tipo/B | pastelaria: lanche rapido/barato provavel; horario sem fonte |
| **1** | Cafeteria Metrô (`1945`) | fast_food | pipeline #5 | 0.64 | tipo/B | sem fonte |
| **1** | Subway (`1170`) | fast_food | pipeline #6 | 0.53 | tipo/B | sanduiches rapidos; sem fonte |
| **1** | Subway (`919`) | fast_food | pipeline #7 | 0.67 | tipo/B | sanduiches rapidos; sem fonte |
| **1** | Grande Café (`1420`) | cafe | pipeline #8 | 0.76 | tipo/B | sem fonte |
| **1** | Subway (`1422`) | fast_food | contraste | 0.77 | tipo/B | contraste; sem fonte |
| **1** | Lanches (`1280`) | fast_food | contraste | 0.62 | tipo/B | contraste; sem fonte |

## TC-16 (clarificar)

**Núcleo:** pedido ambiguo: a resposta correta e perguntar; candidatos nao rotulados

_Sem candidatos rotulados._

## TC-17 (abster)

**Núcleo:** criterio impossivel (patinacao no gelo + 03:30)

_Sem candidatos rotulados._

## TC-18 (abster)

**Núcleo:** fora de escopo (frete)

_Sem candidatos rotulados._

## Fontes consultadas (pesquisa na internet, via WebSearch)

- Biblioteca Nacional de Brasília, clubes de leitura: Jornal de Brasília (clube-de-leitura-se-reune-nesta-quinta-23-na-biblioteca-nacional) e Correio Braziliense (2024/2026).
- Apetit Natural / Greens / Nutri Vida: spinach.guide, HappyCow, Correio Braziliense (2024), curtamais.com.br (2020).
- CineCultura Liberty Mall: guiadasemana.com.br, jornaldebrasilia.com.br (reforma em 2025), theguide.com.br.
- Sushi San (tatame), Sumô, Hana: Correio Braziliense (blog Liana Sabo), curtamais.com.br (rodízio japonês).
- Casa de Chá (Praça dos Três Poderes): Correio Braziliense (2024), Correio da Manhã (2025).
- Carcassonne Pub: Correio Braziliense e Guia da Semana (jogos de tabuleiro).
- Parque da Cidade (pistas e área para cães): Quinto Andar guias; Correio da Manhã 'cães ganham áreas cercadas no DF' (2024).
- Deck Sul (mesas de jogos): Diário do Poder. Jardim Botânico (orquidário): Catraca Livre, Agência Brasília, Quinto Andar.
- Saboretto: Wanderlog. SESI Lab: Portal da Indústria.
- Muitas fontes são antigas (2013–2025) e as próprias respostas recomendam confirmar horário e endereço atuais.
## Revisão v1.1 (19/11/2026): 3 lugares entregues pelo agente LLM

O experimento do agente LLM entregou 3 lugares que não estavam no pool. Foram rotulados com o mesmo protocolo e entram no gabarito
(`rotulos_osm_v1.json`, `versao = v1.1`), para que pipeline e agente sejam comparados com os mesmos rótulos:

| Caso | Lugar | Grau | Motivo |
|---|---|:-:|---|
| TC-12 | Parque Ana Lídia (`way/227022746`) | 1 | parque; mesas de jogos sem fonte |
| TC-15 | Entre Eixos (`node/4716974234`) | 0 | OSM abre 09:00-17:00; o pedido é "aberto até às 22h" |
| TC-15 | Melbourne Café & Co. (`node/5416977721`) | 0 | OSM Seg-Sex 08:15-17:30; idem |

Os scores gravados no Langfuse para os runs anteriores foram calculados com os rótulos da época. Para comparar com o gabarito atual use
`python scripts/avaliacao/recalcular_scores.py <run> <run>`.
