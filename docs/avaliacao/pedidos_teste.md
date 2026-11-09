# Conjunto de Testes Pré-Ajuste (Benchmark Dataset)

Este documento registra o **conjunto formal de 18 pedidos de teste** concebidos e congelados **antes de qualquer ajuste no sistema**, conforme metodologia estrita de avaliação independente. O conjunto cobre o espectro psicossocial identificado nas personas do projeto (jovens adultos com rotinas corridas, idosos com mobilidade reduzida ou receio de tecnologia, introvertidos, cinéfilos e pessoas em busca de reconexão social), além de conter casos de borda e estresse obrigatórios.

---

## 1. Critérios Formais de Aceitabilidade de um Local

Para que uma recomendação gerada pela IA ou pelo mecanismo RAG seja classificada como **aceitável (relevante e segura)**, ela deve cumprir rigorosamente as seguintes 5 dimensões de qualidade:

1. **Segurança e Espaço Público/Comercial Verificado (RNF01):**
   - O local deve ser obrigatoriamente um espaço público (parque, praça, centro cultural) ou estabelecimento comercial verificado (café, bistrô, restaurante, livraria) cadastrado na base oficial (OpenStreetMap / PostGIS).
   - Espaços residenciais privados, locais abandonados ou áreas com alerta de insegurança são **estritamente inaceitáveis** (tolerância zero).
2. **Relevância Semântica e Adequação à Atividade:**
   - O estabelecimento deve viabilizar concretamente a atividade solicitada pelo usuário (ex.: mesas adequadas para jogos de tabuleiro; ambiente com acústica tratada para conversa e leitura; trilhas planas para caminhada).
3. **Compatibilidade Psicossocial e "Vibe":**
   - Se o usuário especificar perfil introvertido ou conversa profunda, o local deve ter baixo nível de ruído e disposição espacial adequada (mesas espaçadas). Locais excessivamente barulhentos são inaceitáveis para essa intenção.
4. **Acessibilidade e Restrições Específicas:**
   - Quando declarada a necessidade de acessibilidade (ex.: mobilidade reduzida de idosos ou usuários em cadeiras de rodas), o local deve ter atributo `wheelchair: yes` ou acesso comprovadamente plano e sem escadarias impeditivas.
5. **Viabilidade Logística e Operacional:**
   - O local deve estar localizado dentro do raio aceitável em relação ao ponto de referência informado ($\le 5\text{ km}$ a $10\text{ km}$) e possuir horário de funcionamento compatível com o turno pretendido (manhã, tarde ou noite).

---

## 2. Tabela Resumo dos Pedidos de Teste

| ID | Persona / Perfil | Pedido do Usuário | Tipo | Restrições-Chave | Ação Esperada do Sistema |
|---|---|---|---|---|---|
| **TC-01** | Dona Helena (Idosa, 68a) | Café calmo e plano na Asa Sul para conversar pela manhã | Padrão | Acessibilidade PCD, Silêncio, Manhã, Asa Sul | Recomendar cafés tranquilos e acessíveis |
| **TC-02** | Carla Mendes (Jovem, 29a) | Lugar descontraído no fim de tarde para jogos de tabuleiro | Padrão | Mesas amplas, Descontraído, Fim de tarde | Recomendar ludotecas/cafés com jogos |
| **TC-03** | Introvertido (34a, TI) | Espaço silencioso para leitura e debate de ficção científica | Padrão | Silencioso, Livros/Cultura, Baixo ruído | Recomendar livrarias com café ou centros culturais |
| **TC-04** | Idoso (72a, aposentado) | Parque aberto com pistas planas para caminhada leve matinal | Padrão | Pistas planas, Banheiros, Manhã, Natureza | Recomendar parques públicos urbanos planos |
| **TC-05** | Universitária (22a) | Cafeteria com tomadas e mesinhas para estudo em grupo | Padrão | Wi-Fi, Tomadas, Mesas coletivas | Recomendar cafeterias com perfil coworking |
| **TC-06** | Extrovertido (31a) | Feirinha gastronômica ao ar livre no sábado à noite | Padrão | Gastronomia externa, Noite, Interativo | Recomendar polos de food trucks ou praças gastronômicas |
| **TC-07** | Vegano/Vegetariano (27a) | Restaurante com culinária vegetal na Asa Norte para almoço | Padrão | Cardápio vegetariano/vegano, Almoço, Asa Norte | Recomendar restaurantes vegetarianos verificados |
| **TC-08** | Cinéfilo (35a) | Cinema de rua ou alternativo com café para debate pós-sessão | Padrão | Cinema alternativo, Noite, Café adjacente | Recomendar cineclubes e centros culturais |
| **TC-09** | Dona Helena (Idosa, 68a) | Ateliê ou centro de convivência para oficina de cerâmica | Padrão | Oficinas manuais, Seguro, Tarde | Recomendar centros culturais públicos com cursos |
| **TC-10** | Tutor de Pet (25a) | Parque pet friendly com cercado para cães socializarem | Padrão | Área cercada pet, Ar livre | Recomendar parques com parcão cercado |
| **TC-11** | Tímido (40a) | Chá da tarde com mesas bem espaçadas e discreto | Padrão | Muito calmo, Privacidade espacial | Recomendar casas de chá acústicas e intimistas |
| **TC-12** | Desportista Leve (45a) | Parque com mesas de xadrez ou ping-pong públicas | Padrão | Esporte recreativo gratuito, Ar livre | Recomendar parques com mesas recreativas fixas |
| **TC-13** | Jovem Gastronômico (26a) | Restaurante japonês agradável com tatames na Asa Sul | Padrão | Culinária japonesa, Asa Sul, Confraternização | Recomendar sushi bar de qualidade verificado |
| **TC-14** | Senhoras 60+ | Jardim botânico ou orquidário com bancos para domingo de manhã | Padrão | Jardim botânico, Trilhas planas, Domingo manhã | Recomendar jardim botânico ou parques ecológicos |
| **TC-15** | Universitário Noturno (23a)| Café cultural perto de universidade aberto até 22h e barato | Padrão | Preço acessível, Horário noturno, Cultural | Recomendar cafés universitários alternativos |
| **TC-16** | Indeciso / Vago | *"Quero sair para algum lugar legal para espairecer ou encontrar gente"* | **Ambíguo** | Nenhuma especificação de atividade ou local | Solicitar desambiguação amigável e oferecer opções contrastantes seguras |
| **TC-17** | Pedido Impossível | *"Cafeteria vegana com pista de patinação no gelo na Asa Sul às 03:30 da madrugada"* | **Sem Resultado** | Culinária vegana + patinação no gelo + 03:30h da manhã | **Abstenção correta**: Declarar inexistência de correspondência e sugerir relaxamento |
| **TC-18** | Fora de Escopo | *"Frete com caminhão baú para transportar móveis no próximo sábado"* | **Fora do Escopo** | Mudança/frete de carga residencial | **Abstenção correta**: Recusar serviço de transporte e orientar sobre foco em encontros sociais |

---

## 3. Protocolo de Avaliação Pré-Ajuste

1. **Congelamento:** Nenhuma das 18 frases foi alterada durante o desenvolvimento do pipeline de busca semântica e cálculo de score.
2. **Avaliação Cega:** A rotulação do que é aceitável foi estabelecida *a priori*, garantindo que os algoritmos sejam mensurados estritamente pelo atendimento aos critérios estabelecidos.
3. **Métricas Aplicadas:** Precision@3 em cada consulta válida, cálculo da Fundamentação das justificativas contra os metadados do banco (PostGIS), taxa de existência real dos locais sugeridos (meta 100%) e verificação formal da abstenção nos casos TC-17 e TC-18.

