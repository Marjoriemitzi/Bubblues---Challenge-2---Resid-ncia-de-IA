# Bubbles

Ecossistema de mediação logística que conecta adultos e idosos em pequenos grupos presenciais (3 a 8 pessoas) em espaços públicos e comerciais seguros para cultivar vínculos comunitários e combater o isolamento social.

## Pessoas e Perfis

**Membro**:
Pessoa adulta ou idosa cadastrada na plataforma que busca participar de encontros presenciais em grupo na sua comunidade.
_Avoid_: Usuário, Cliente, Paciente, Solitário, Isolado

**Perfil Base**:
Conjunto de preferências sociais estáveis, interesses gerais e necessidades permanentes de acessibilidade física declaradas pelo Membro no momento de seu ingresso.
_Avoid_: Cadastro, Ficha Clínica, Cluster, Histórico Psicológico

**Acessibilidade Física**:
Condição permanente ou temporária de mobilidade motora do Membro (como uso de cadeira de rodas, necessidade de rampas ou locais planos) que atua como critério eliminatório na seleção de espaços.
_Avoid_: Deficiência, Limitação, Tag de Cadeirante, Restrição Suave

**Tolerância Sensorial**:
Nível máximo de estímulo acústico e movimentação ambiental (baixo, moderado ou indiferente) em que o Membro consegue interagir e conversar com conforto auditivo e emocional.
_Avoid_: Fobia Social, Nível de Ruído, Silêncio Obrigatório

## Espaços e Descoberta

**Local Verificado**:
Espaço público aberto ou estabelecimento comercial ativo na comunidade cuja existência física, segurança e condições de acesso foram previamente validadas.
_Avoid_: Place, Estabelecimento, Ponto, POI, Local Sugerido

**Vibe**:
Atmosfera subjetiva e propósito de convivência de um Local Verificado ou de um Encontro (como leitura silenciosa, caminhada ao ar livre ou conversa descontraída).
_Avoid_: Categoria, Clima, Humor, Filtro

**Intenção de Encontro**:
Desejo momentâneo expresso pelo Membro por voz ou texto livre (ou inferido proativamente a partir de seu Perfil Base) para realizar uma atividade social em uma região e turno específicos.
_Avoid_: Prompt, Query, Solicitação, Busca

**Afinidade Temática**:
Grau de convergência entre a Intenção de Encontro dos Membros e a proposta de atividade e atmosfera de um Local Verificado.
_Avoid_: Match, Score Vetorial, Clusterização

**Reputação Comunitária**:
Percepção consolidada de qualidade, acolhimento e segurança de um Local Verificado, ponderando a vivência real dos Membros da plataforma e avaliações públicas externas.
_Avoid_: Nota Média, Estrelas, Ranking

**Abstenção Segura**:
Recusa transparente da plataforma em recomendar locais quando uma Intenção de Encontro foge do propósito de convivência social em grupo ou impõe condições fisicamente inexistentes na malha urbana.
_Avoid_: Erro de Busca, Falha, Lista Vazia, Fallback Aleatório

## Dinâmica do Encontro e Compromisso

**Slot de Pareamento**:
Agrupamento em formação vinculado a um Local Verificado e a um turno específico que reúne automaticamente de 3 a 8 Membros com Afinidade Temática compatível.
_Avoid_: Fila, Sala de Espera, Grupo Aberto, Cluster

**Encontro**:
Reunião presencial agendada entre 3 e 8 Membros em um Local Verificado com data e horário definidos.
_Avoid_: Rolê, Evento, Sessão, Consulta, Encontro Individual

**Check-in Final**:
Confirmação definitiva de presença realizada pelos Membros entre 30 e 60 minutos antes do início do Encontro.
_Avoid_: Reserva, RSVP Inicial, Pré-confirmação

**Quórum Mínimo**:
Quantidade mínima obrigatória de Membros confirmados no Check-in Final para que o Encontro ocorra, equivalente à maioria simples do grupo respeitando o piso absoluto e inegociável de 3 Membros confirmados.
_Avoid_: Lotação, Dupla, Encontro 1-a-1

**Pauta Quebra-Gelo**:
Conjunto de três tópicos leves de conversa baseados nas afinidades comuns do grupo, disponibilizado passivamente aos Membros confirmados 30 minutos antes do Encontro para eliminar a ansiedade do primeiro contato.
_Avoid_: Roteiro Obrigatório, Chat de Grupo, Anfitrião Virtual, Bot Mediador

**Desistência Prévia**:
Cancelamento de participação comunicado pelo Membro antes do encerramento da janela do Check-in Final, isento de qualquer penalidade de compromisso.
_Avoid_: Falta, Abandono, No-Show

**No-Show**:
Ausência presencial injustificada de um Membro que havia confirmado presença no Check-in Final, sujeita à perda de pontos de compromisso na plataforma.
_Avoid_: Cancelamento, Desistência, Atraso

