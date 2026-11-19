# Verificação das saídas do NLU (DeepSeek `deepseek-chat`)

Gerado por `scripts/avaliacao/gerar_requests_nlu.py`. ERRO = contradiz o pedido; REVISAR = plausível, mas um humano deve olhar.

## TC-01 (Padrao, esperado: recomendar)
> Gostaria de um café calmo e tranquilo na Asa Sul, com boa acessibilidade para caminhar sem escadas, para conversar com pessoas da minha faixa etária pela manhã.

- ação obtida: **recomendar** | categorias: `['cafe']` | região: `Asa Sul` | ruído: `baixo` | acessib.: `{'wheelchair_required': True, 'elder_friendly': True, 'pet_friendly': False}`
- atividade: tomar café e conversar | vibe: calmo e tranquilo | foco: `['calmo', 'tranquilo', 'acessível', 'conversa']` | horário: `{'preferred_time_slot': 'manha', 'specific_hours': None}`
- sem achados

## TC-02 (Padrao, esperado: recomendar)
> Procuro um lugar descontraído no final de tarde para encontrar um grupo pequeno para jogar jogos de tabuleiro ou bater papo tomando um suco ou cerveja artesanal.

- ação obtida: **recomendar** | categorias: `['bar', 'cafe', 'pub']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: jogar jogos de tabuleiro ou bater papo | vibe: descontraído | foco: `['descontraído', 'grupo pequeno', 'jogos de tabuleiro', 'suco', 'cerveja artesanal']` | horário: `{'preferred_time_slot': 'tarde', 'specific_hours': None}`
- sem achados

## TC-03 (Padrao, esperado: recomendar)
> Um espaço silencioso e aconchegante para leitura em grupo e debate sobre livros de ficção científica, de preferência integrado a uma livraria ou centro cultural.

- ação obtida: **recomendar** | categorias: `['library', 'community_centre', 'arts_centre']` | região: `None` | ruído: `baixo` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: leitura em grupo e debate sobre livros | vibe: silencioso e aconchegante | foco: `['silencioso', 'aconchegante', 'leitura', 'debate', 'livraria']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados

## TC-04 (Padrao, esperado: recomendar)
> Parque aberto com pistas planas e sombras de árvores para uma caminhada leve em grupo no início da manhã, seguido de conversa em banco de praça.

- ação obtida: **recomendar** | categorias: `['park']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: caminhada leve em grupo e conversa em banco de praça | vibe: tranquilo, arborizado, plano | foco: `['pistas planas', 'sombras de árvores', 'caminhada leve', 'banco de praça', 'grupo']` | horário: `{'preferred_time_slot': 'manha', 'specific_hours': None}`
- **ERRO** `wheelchair_required`: pedido exige acessibilidade e o NLU deixou false

## TC-05 (Padrao, esperado: recomendar)
> Cafeteria com mesinhas externas e tomadas, onde seja comum ver pessoas estudando ou trabalhando em grupo com laptops.

- ação obtida: **recomendar** | categorias: `['cafe']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: estudar ou trabalhar em grupo com laptops | vibe: tranquilo, produtivo | foco: `['mesas externas', 'tomadas', 'estudantes', 'trabalho em grupo', 'laptops']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados

## TC-06 (Padrao, esperado: recomendar)
> Gostaria de uma praça gastronômica ou feirinha ao ar livre com música ambiente moderada no sábado à noite para interagir com novas pessoas.

- ação obtida: **recomendar** | categorias: `['food_court']` | região: `None` | ruído: `moderado` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: interagir com novas pessoas em praça gastronômica ou feirinha ao ar livre | vibe: música ambiente moderada, social | foco: `['ao ar livre', 'gastronômico', 'feirinha', 'música ambiente', 'social']` | horário: `{'preferred_time_slot': 'noite', 'specific_hours': 'sábado à noite'}`
- sem achados

## TC-07 (Padrao, esperado: recomendar)
> Restaurante com culinária saudável e vegetariana/vegana na Asa Norte, com espaço arejado e cardápio vegetal para um almoço de socialização.

- ação obtida: **recomendar** | categorias: `['restaurant']` | região: `Asa Norte` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: almoço de socialização | vibe: saudável, arejado, vegetariano/vegano | foco: `['saudável', 'vegetariano', 'vegano', 'arejado', 'socialização']` | horário: `{'preferred_time_slot': 'tarde', 'specific_hours': None}`
- sem achados

## TC-08 (Padrao, esperado: recomendar)
> Cinema de rua ou espaço exibidor de filmes alternativos com cafeteria integrada para debate pós-sessão com os outros participantes.

- ação obtida: **recomendar** | categorias: `['cinema', 'cafe']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: assistir filme alternativo e debater com cafeteria | vibe: alternativo, debate | foco: `['cinema alternativo', 'cafeteria', 'debate', 'espaço cultural']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados

## TC-09 (Padrao, esperado: recomendar)
> Ateliê comunitário ou centro de convivência público para oficina de cerâmica ou artesanato em grupo na parte da tarde.

- ação obtida: **recomendar** | categorias: `['community_centre', 'arts_centre']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: oficina de cerâmica ou artesanato em grupo | vibe: indefinida | foco: `['oficina', 'cerâmica', 'artesanato', 'grupo']` | horário: `{'preferred_time_slot': 'tarde', 'specific_hours': None}`
- sem achados

## TC-10 (Padrao, esperado: recomendar)
> Parque ou praça pet friendly com cercado para cachorros, onde tutores costumam se reunir para deixar os pets brincarem e socializarem.

- ação obtida: **recomendar** | categorias: `['park', 'playground']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': True}`
- atividade: levar cachorro para brincar e socializar | vibe: pet friendly, social | foco: `['cercado para cães', 'socialização de pets', 'encontro de tutores']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados

## TC-11 (Padrao, esperado: recomendar)
> Quero um chá da tarde em ambiente muito discreto e pouco barulhento, com mesas espaçadas para conversar sem me sentir vigiado.

- ação obtida: **recomendar** | categorias: `['cafe']` | região: `None` | ruído: `baixo` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: chá da tarde | vibe: discreto e reservado | foco: `['discreto', 'silencioso', 'mesas espaçadas', 'privacidade']` | horário: `{'preferred_time_slot': 'tarde', 'specific_hours': None}`
- sem achados

## TC-12 (Padrao, esperado: recomendar)
> Quadra pública ou parque com mesas de ping-pong ou xadrez ao ar livre para encontrar parceiros de partida recreativa sem custo.

- ação obtida: **recomendar** | categorias: `['park', 'pitch']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: jogar ping-pong ou xadrez ao ar livre | vibe: recreativa | foco: `['mesas de jogos', 'ping-pong', 'xadrez', 'gratuito', 'parceiros']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados

## TC-13 (Padrao, esperado: recomendar)
> Quero comer sushi e comida japonesa fresca num restaurante agradável na Asa Sul com mesas coletivas ou tatames aconchegantes.

- ação obtida: **recomendar** | categorias: `['restaurant']` | região: `Asa Sul` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: comer sushi e comida japonesa | vibe: agradável, aconchegante | foco: `['japonesa', 'fresca', 'mesas coletivas', 'tatames', 'aconchegante']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados

## TC-14 (Padrao, esperado: recomendar)
> Espaço com jardim florido ou orquidário com banquinhos à sombra para conversar e tomar uma água de coco na manhã de domingo.

- ação obtida: **recomendar** | categorias: `['garden', 'park']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: conversar e tomar água de coco em jardim florido | vibe: tranquilo, florido, com sombra | foco: `['jardim florido', 'orquidário', 'sombra', 'banquinhos', 'água de coco']` | horário: `{'preferred_time_slot': 'manha', 'specific_hours': None}`
- **ERRO** `wheelchair_required`: pedido exige acessibilidade e o NLU deixou false

## TC-15 (Padrao, esperado: recomendar)
> Lanchonete ou café cultural perto da universidade aberto até às 22h com clima jovem e opções de lanches rápidos e baratos.

- ação obtida: **recomendar** | categorias: `['cafe', 'fast_food']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: lanchar em café cultural | vibe: jovem | foco: `['universidade', 'jovem', 'lanches rápidos', 'barato', 'cultural']` | horário: `{'preferred_time_slot': None, 'specific_hours': 'até 22h'}`
- sem achados

## TC-16 (Ambiguo, esperado: clarificar)
> Quero sair para algum lugar legal para espairecer ou encontrar gente, qualquer coisa bacana serve.

- ação obtida: **clarificar** | categorias: `['park', 'community_centre', 'cafe']` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: espairecer e encontrar gente | vibe: indefinida | foco: `['social', 'descontraído', 'público']` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- pergunta: Você prefere um lugar mais tranquilo ou mais movimentado?
- sem achados

## TC-17 (Sem_Resultado_Possivel, esperado: abster)
> Procuro uma cafeteria vegana com pista de patinação no gelo e música ao vivo na Asa Sul aberta às 03:30 da madrugada de segunda-feira.

- ação obtida: **abster** | categorias: `['cafe']` | região: `Asa Sul` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: cafeteria vegana com patinação no gelo e música ao vivo | vibe: indefinida | foco: `['vegano', 'música ao vivo']` | horário: `{'preferred_time_slot': 'madrugada', 'specific_hours': '03:30'}`
- sem achados

## TC-18 (Fora_De_Escopo, esperado: abster)
> Preciso urgente de um frete com caminhão baú e 2 carregadores para transportar meus móveis da Asa Norte até Taguatinga no próximo sábado.

- ação obtida: **abster** | categorias: `[]` | região: `None` | ruído: `indiferente` | acessib.: `{'wheelchair_required': False, 'elder_friendly': False, 'pet_friendly': False}`
- atividade: contratar frete para mudança | vibe: indefinida | foco: `[]` | horário: `{'preferred_time_slot': None, 'specific_hours': None}`
- sem achados
