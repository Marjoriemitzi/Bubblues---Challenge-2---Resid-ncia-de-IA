# Residência em IA - Grupo 10: Definição de Projeto

Este documento detalha a definição de projeto do Grupo 10, focada em conectar pessoas e combater a solidão através da Inteligência Artificial.

---

## 1. Cenário escolhido

O cenário escolhido pelo Grupo 10 aborda o combate à solidão e ao isolamento social em adultos e idosos por meio do uso de inteligência artificial para viabilizar e incentivar encontros presenciais em grupo. A solidão tem se consolidado como um desafio crítico de saúde pública global, impactando negativamente o bem-estar mental, físico e social. Diante desse panorama, o projeto propõe a construção de um ecossistema inteligente (combinando modelos de linguagem e aprendizado de máquina) que reduz atritos operacionais e a sobrecarga cognitiva na organização de encontros, conectando pessoas desconhecidas com alta compatibilidade em locais públicos e seguros de sua comunidade.

## 2. Problema

Para embasamento metodológico, realizou-se uma síntese de evidências por meio de revisão sistemática com dois revisores independentes, utilizando formulário padronizado, síntese narrativa e contagem de votos.

Ao analisar 32 estudos sobre o tema, observou-se que as intervenções que apresentaram maior impacto positivo na promoção da saúde social, mental e física compartilham características centrais:

*   **Formatos coletivos e participativos:** $79\%$ das iniciativas em grupo e mais de $80\%$ das abordagens participativas obtiveram êxito, em comparação a apenas $55\%$ das individuais e $44\%$ das não participativas.
*   **Fundamentação teórica consistente:** $87\%$ das intervenções estruturadas sobre teorias consolidadas tiveram sucesso, contra $59\%$ daquelas sem base clara.
*   **Atividades práticas e de suporte:** Intervenções baseadas em atividades ($86\%$) e em redes de apoio ($80\%$) mostraram-se muito superiores a visitas domiciliares ($60\%$) ou treinamentos exclusivamente virtuais ($25\%$).
*   **Foco na integração comunitária ampla:** Ações não restritas estritamente a um rótulo de isolamento alcançaram $80\%$ de eficácia, superando os $58\%$ das focadas apenas em idosos isolados.

Esses achados reforçam a premissa do nosso projeto: para combater eficazmente a solidão, as soluções tecnológicas devem facilitar encontros presenciais em grupo, fundamentados no engajamento ativo, no apoio mútuo e na construção coletiva de conexões humanas significativas.

### 2.1. Qual o nosso problema? O que queremos resolver usando LLM e ML?

Nosso problema é: **Como projetar um ecossistema de IA (LLM e ML) que empodere adultos a compreenderem suas necessidades sociais sem atrito, automatizando a logística para que possam decidir melhor sobre encontros presenciais, com o objetivo final de combater a solidão e viver melhor.**

Surgem algumas questões, que também podem ser tratadas como *guiding questions*:

*   Como podemos projetar um sistema de recomendação baseado em IA que compreenda as barreiras psicossociais da população, apoiando a tomada de decisão no engajamento em atividades locais de forma ética, segura e mensurável, com o objetivo de reduzir o isolamento social?
*   Como projetar um algoritmo baseado em IA que forme grupos altamente compatíveis de desconhecidos para encontros presenciais, mitigando riscos de segurança e a alta taxa de desistência, com o objetivo de combater a epidemia de solidão entre adultos?
*   Por que os adultos têm tanta dificuldade em fazer novos amigos na vida moderna e como um modelo gratuito pode criar o senso de compromisso necessário para que as pessoas realmente compareçam ao encontro presencial?
*   Combater a solidão entre jovens adultos e pessoas mais idosas é possível usando tecnologia?
*   Mitigar a sobrecarga cognitiva de marcar encontros presenciais para diminuir a solidão é realmente um problema?
*   Quais são os reais motivadores da solidão no público e quais barreiras (físicas, cognitivas, emocionais ou de letramento digital) os impedem de buscar novas conexões sociais na comunidade hoje?

### 2.2. Algumas respostas para nossas perguntas

O problema contemporâneo não é apenas a falta de opções, mas a sobrecarga de informações e a fadiga de decisão. Ao tentar organizar um encontro, as pessoas desistem diante da complexidade de alinhar agendas, gostos e locais. A IA entra para compreender melhor a intenção subjetiva do usuário. 

Em vez de forçar a pessoa a preencher formulários frios, o sistema usa LLM para interpretar um desejo simples (ex: *"Quero um café tranquilo para conversar sobre tecnologia"*). A IA compreende a "vibe" e o contexto, removendo a barreira inicial da interação. Então, a tecnologia empodera o usuário a decidir melhor porque ela faz o trabalho pesado de cruzamento de dados.

### 2.3. Fontes que embasam o problema

!!! quote "O impacto da Solidão"
    A solidão afeta pessoas de todas as idades, especialmente jovens e pessoas que vivem em países de baixa e média renda (LMIC). Entre $17\%$ a $21\%$ dos indivíduos com idade entre 13 e 29 anos relataram se sentir solitários, com as taxas mais altas entre os adolescentes. Cerca de $24\%$ das pessoas em baixa renda relataram se sentir solitárias, o dobro da taxa em países de alta renda (cerca de $11\%$).

A pessoa tem companhia, mas ninguém toma a iniciativa de organizar algo. Sem perfis. Sem deslizar a tela. Sem organizar nada. A gente forma o seu grupo e cuida dos detalhes. Você só precisa aparecer.

Mesmo em um mundo conectado digitalmente, muitos jovens se sentem sozinhos. À medida que a tecnologia remodela nossas vidas, devemos garantir que ela fortaleça, não enfraqueça, a conexão humana. Em contraste, a solidão e o isolamento social aumentam o risco de derrame, doenças cardíacas, diabetes, declínio cognitivo e morte prematura. Também afeta a saúde mental, com pessoas solitárias com duas vezes mais chances de ficarem deprimidas. A solidão também pode levar à ansiedade e pensamentos de automutilação ou suicídio.

A proporção de pessoas idosas na sociedade aumentou nas últimas décadas, e estima-se que aproximadamente $25\%$ da população terá 60 anos ou mais nos próximos 20 a 40 anos. O isolamento social é predominante entre os idosos e as evidências indicam o efeito prejudicial que ele pode ter na saúde e no bem-estar. O objetivo desta revisão foi avaliar a eficácia de intervenções destinadas a aliviar o isolamento social e a solidão em idosos.

## 3. Mapa de Stakeholders e Personas

### 3.1. Personas

!!! info "Persona 1: Carla Mendes (Adulto com rotina corrida)"
    * **Idade:** 29 anos | **Profissão:** Analista de Marketing | **Cidade:** São Paulo - SP
    * **Objetivo:** Conhecer pessoas com interesses semelhantes, participar de atividades sociais e fazer novas amizades.
    * **Desafios:** Conciliar agenda, organizar encontros e confiar na segurança da plataforma.
    * **O que valoriza:** Recomendações personalizadas, praticidade, ambiente seguro e experiências significativas.
    * **Citação:** *"Quero sair da rotina, conhecer gente nova e participar de algo que eu realmente goste."*

!!! info "Persona 2: Dona Helena Souza (Pessoa idosa em busca de convivência)"
    * **Idade:** 68 anos | **Profissão:** Aposentada | **Cidade:** Belo Horizonte - MG
    * **Objetivo:** Participar de atividades presenciais, ampliar seu circulo social e se sentir mais ativa.
    * **Desafios:** Ter dificuldade com tecnologia, receio de ambientes desconhecidos e limitações de mobilidade.
    * **O que valoriza:** Facilidade de uso, segurança, apoio da comunidade e atividades próximas de sua região.
    * **Citação:** *"Quero companhia, fazer novas amizades e aproveitar melhor a vida."*

### 3.2. Mapa de Stakeholders

| Stakeholder | Interesse | Poder | Estratégia |
| :--- | :--- | :--- | :--- |
| **Usuários do aplicativo** | Alto | Médio ou baixo | Entrevistar e testar soluções |
| **Equipe de desenvolvimento** | Alto | Alto | Participar das decisões |
| **Patrocinador** | Alto | Alto | Apresentar resultados |
| **Parceiros de eventos** | Médio | Médio | Construir parcerias |
| **Especialista em privacidade** | Alto | Médio ou alto | Consultar sobre riscos e LGPD |

### 3.3. Matriz de Poder e Interesse

A categorização dos stakeholders baseia-se na sua influência e interesse no projeto:

*   **Gerenciar de Perto (Alto poder, alto interesse):** Equipe do projeto, Especialistas em segurança e privacidade, Instituições de saúde e bem-estar.
*   **Manter Satisfeitos (Alto poder, baixo interesse):** Patrocinadores e investidores, Parceiros estratégicos, Órgãos reguladores.
*   **Manter Informados (Baixo poder, alto interesse):** Usuários (adultos e idosos), Organizadores de eventos, Famílias e rede de apoio, Sociedade em geral.
*   **Monitorar (Baixo poder, baixo interesse):** Comunidade em geral, Estabelecimentos sem parceria ativa, Fornecedores não estratégicos.

## 4. Requisitos

### 4.1. Requisitos Funcionais (RF)

*   **RF01 - Interpretação de Intenção e Necessidades Sociais via PLN:** O sistema deve utilizar Processamento de Linguagem Natural (LLM) para extrair preferências, intenções subjetivas, restrições e horários a partir de solicitações em texto livre do usuário.
*   **RF02 - Recomendação e Formação de Grupos Compatíveis:** O algoritmo (ML) deve agrupar usuários desconhecidos com base em interesses em comum, perfil psicossocial e compatibilidade de agenda/localização.
*   **RF03 - Automação da Logística de Encontros:** O sistema deve sugerir automaticamente locais públicos seguros (ex: cafés, parques) e horários adequados, reduzindo o esforço logístico dos participantes.
*   **RF04 - Coleta de Feedback Pós-Encontro:** O sistema deve disponibilizar uma avaliação simples de satisfação e segurança (nota de 1 a 5) logo após a realização de cada encontro presencial.

### 4.2. Requisitos Não Funcionais (RNF)

*   **RNF01 - Segurança e Seleção de Locais Públicos (Guardrails):** $100\%$ das sugestões automáticas de encontros devem ser restritas a locais públicos verificados e abertos, garantindo a integridade dos participantes.
*   **RNF02 - Privacidade e Proteção de Dados (LGPD):** A coleta de dados deve ser minimizada estritamente ao necessário; textos e dados pessoais livres não devem ser retidos indevidamente.
*   **RNF03 - Usabilidade e Baixa Carga Cognitiva:** A interface deve ser acessível e de fácil utilização para diferentes perfis (jovens e idosos com baixo letramento digital), sem a necessidade de preenchimento de formulários extensos.
*   **RNF04 - Desempenho e Precisão do Ranking:** As recomendações de locais e grupos devem responder com alta precisão e em poucos minutos entre a solicitação inicial e a confirmação do usuário.

## 5. Riscos

### Riscos Comportamentais e de Produto

!!! warning "Risco de No-Show (Falta aos encontros)"
    Por ser um modelo gratuito, há uma alta probabilidade de desistência de última hora, o que pode frustrar os usuários que comparecerem.
    **Mitigação:** Implementar um sistema de reputação no aplicativo. Usuários que confirmaram presença e faltam sem justificativa perdem "pontos" ou sofrem suspensão temporária de uso.

!!! warning "Risco de Incompatibilidade Extrema"
    O algoritmo de clusterização falhar ao capturar nuances comportamentais, gerando um grupo sem química (ex: conflitos de opiniões sensíveis).
    **Mitigação:** O LLM ficará na extração objetiva de "vibes" e interesses (JSON) para o algoritmo de Machine Learning. O aplicativo também aplicará a métrica de Satisfação do encontro (meta de média $\ge 4$) para retroalimentar e ajustar o peso das variáveis no modelo.

### Riscos Técnicos

!!! warning "Risco de Alucinação do LLM (Locais Inexistentes/Fechados)"
    A inteligência artificial gerar ou sugerir um estabelecimento que fechou permanentemente ou que não comporta grupos.
    **Mitigação:** O LLM não tomará a decisão final do local. Ele apenas extrairá a intenção do texto. A decisão do local será feita cruzando esses dados com ferramentas de Mapas (ex: API do Google Places) em tempo real, garantindo a verificação automática contra bases atualizadas.

### Riscos de Segurança Física e Privacidade

!!! warning "Risco à Segurança Física dos Usuários"
    Encontros presenciais entre desconhecidos podem expor os usuários (especialmente mulheres e idosos) a situações de vulnerabilidade.
    **Mitigação:** Estabelecer uma "guardrail" rígida no sistema onde $100\%$ dos locais sugeridos devem ser, obrigatoriamente, espaços públicos ou estabelecimentos comerciais verificados, movimentados e em horários adequados.

!!! warning "Risco de Vazamento de Dados Sensíveis"
    Exposição de rotinas, localização em tempo real e desabafos dos usuários nas caixas de texto.
    **Mitigação:** A coleta será limitada ao estritamente necessário para o "match", e os dados de texto livre enviados para o LLM não serão retidos no banco de dados após a extração das entidades (JSON).

## 6. Premissas

### Premissas do Problema e do Usuário

*   **A dor não é a falta de vontade, é a fadiga de decisão:** Assume-se que as pessoas têm o desejo latente de socializar, mas a sobrecarga cognitiva (organizar agendas, escolher locais, quebrar o gelo) atua como a principal barreira para que os encontros aconteçam.
*   **Formato de grupo é mais eficaz:** Assume-se, com base nas evidências metodológicas levantadas (revisão de 32 estudos), que intervenções sociais em formatos coletivos e participativos têm um impacto superior ($79\%$ de êxito) na promoção da saúde física e mental em comparação a soluções individuais.
*   **Acessibilidade Tecnológica Mínima:** Assume-se que o público-alvo possui letramento digital suficiente para interagir com uma interface conversacional simples (baseada em chat/texto livre ou áudio) via smartphone.

### Premissas Tecnológicas

*   **Capacidade de Extração do LLM:** Assume-se que Modelos de Linguagem de Larga Escala (LLMs) atuais são capazes de interpretar com alta precisão a linguagem natural humana e extrair os parâmetros necessários (atividade, local, horário) para estruturar os dados com assertividade (meta de acerto $\ge 85\%$).
*   **Disponibilidade de APIs de Terceiros:** Assume-se o funcionamento e a confiabilidade de bases de mapas externas (como Google Maps ou TripAdvisor) para fornecer, em tempo real, o raio de distância, status de funcionamento e tipo do local para a consolidação do encontro.
*   **O Papel Delimitado da IA:** Assume-se que a Inteligência Artificial não substitui a conexão humana, atuando única e exclusivamente como uma ponte logística para facilitar o encontro presencial no mundo físico.

## 7. Métricas de sucesso

| Métrica | Como medir | Meta sugerida | Pilar |
| :--- | :--- | :--- | :--- |
| **Acerto na interpretação do pedido** | 50 frases escritas pelo grupo e rotuladas à mão (atividade, tipo de local, horário, restrições). Calcular a % de campos extraídos corretamente | $\ge 85\%$ | Compreender melhor (a IA entender o que a pessoa quer) |
| **Pedidos que não precisaram de correção** | % de usuários que confirmam a interpretação sem precisar editar | $\ge 80\%$ | Compreender melhor |
| **Locais sugeridos que existem, estão abertos e dentro do raio** | Verificação automática contra a base de mapas | $100\%$ | Decidir melhor (a IA reduz o esforço e melhora a escolha) |
| **Aceitação da sugestão de local** | % de recomendações em que o usuário escolhe uma das 3 primeiras | $\ge 60\%$ | Decidir melhor |
| **Qualidade do ranking** | Precision@3 avaliada por pessoas | $\ge 0,7$ | Decidir melhor |
| **Tempo do pedido à decisão** | Minutos entre escrever o desejo e confirmar o encontro | $\le 3 \text{ min}$ | Decidir melhor |

## 8. Guiding Questions

1.  Como projetar um ecossistema de IA (LLM e ML) que empodere adultos a compreenderem suas necessidades sociais sem atrito, automatizando a logística para que possam decidir melhor sobre encontros presenciais, com o objetivo final de combater a solidão e viver melhor?
2.  Como podemos projetar um sistema de recomendação baseado em IA que compreenda as barreiras psicossociais da população, apoiando a tomada de decisão no engajamento em atividades locais de forma ética, segura e mensurável, com o objetivo de reduzir o isolamento social?
3.  Como projetar um algoritmo baseado em IA que forme grupos altamente compatíveis de desconhecidos para encontros presenciais, mitigando riscos de segurança e a alta taxa de desistência, com o objetivo de combater a epidemia de solidão entre adultos?
4.  Por que os adultos têm tanta dificuldade em fazer novos amigos na vida moderna?
5.  Como um modelo gratuito pode criar o senso de compromisso necessário para que as pessoas realmente compareçam ao encontro presencial?
6.  Combater a solidão entre jovens adultos e pessoas mais idosas é possível usando tecnologia?
7.  Mitigar a sobrecarga cognitiva de marcar encontros presenciais para diminuir a solidão é realmente um problema?
8.  Quais são os reais motivadores da solidão no público e quais barreiras (físicas, cognitivas, emocionais ou de letramento digital) os impedem de buscar novas conexões sociais na comunidade hoje?
9.  Como identificar quais tipos de atividades presenciais têm maior potencial de gerar conexões sociais duradouras entre os participantes?
10. Quais elementos da experiência do primeiro encontro influenciam a disposição dos participantes em participar de novos encontros?
11. Como atualizar as recomendações conforme os interesses e as preferências dos usuários evoluem ao longo do tempo?
12. Como detectar padrões de comportamento que indiquem que determinadas atividades ou formatos de encontro não estão promovendo boas experiências sociais?
13. Como garantir que os benefícios sociais da plataforma sejam acessíveis também a pessoas com pouco acesso à internet ou baixa familiaridade com ferramentas digitais?
14. Como criar mecanismos de confiança entre pessoas desconhecidas antes da realização de encontros presenciais, sem comprometer a privacidade dos participantes?
15. Como estimular a continuidade das relações sociais construídas nos encontros para que os participantes desenvolvam vínculos de amizade ao longo do tempo?
16. Quais indicadores permitem avaliar se a participação nos encontros está contribuindo para melhorar o bem-estar social e a percepção de pertencimento dos usuários?
17. Como o sistema pode lidar com cancelamentos de última hora e reorganizar os grupos sem prejudicar a experiência dos demais participantes?
18. Como evitar que as recomendações favoreçam sempre os mesmos perfis de usuários ou atividades, limitando a diversidade de experiências e conexões sociais?
19. Como determinar a frequência ideal de encontros presenciais para incentivar a criação de vínculos sem gerar sobrecarga ou desinteresse nos participantes?
20. Como incorporar o feedback dos participantes para identificar falhas na experiência dos encontros e aprimorar continuamente a plataforma?
21. Como avaliar se os resultados obtidos pela plataforma são mantidos a longo prazo, mesmo quando os usuários deixam de depender das recomendações automatizadas?

## 9. Essential Question da equipe

> **"Como ajudar pessoas a criar vínculos significativos por meio de encontros presenciais de forma segura?"**