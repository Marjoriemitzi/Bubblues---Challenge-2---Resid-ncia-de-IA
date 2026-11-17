---
status: accepted
---

# Separação entre Barreiras Físicas/Sensoriais Persistentes (Hard Filters) e Estados Emocionais Efêmeros

Ao investigar os motivadores da solidão e as barreiras de acesso (Guiding Question #8), identificamos dois riscos opostos: reter desabafos emocionais no banco viola a minimização de dados (LGPD / RNF02) e cria estigma clínico, enquanto tratar barreiras físicas e acústicas apenas como pesos suaves (`0.20` de compatibilidade) permite que locais sem rampa (`wheelchair=no`) ou barulhentos (`nivel_ruido=Alto`) entrem no Top-3 de idosos e cadeirantes. Decidimos persistir no Perfil Base exclusivamente condições objetivas de Acessibilidade Física e Tolerância Sensorial — aplicando-as como filtros eliminatórios rígidos (*Hard Filters*) antes do ranqueamento — e processar estados emocionais ou relatos pessoais apenas em memória volátil durante a inferência da LLM, descartando o texto livre imediatamente após a extração estruturada.

## Consequences

- **Garantia de segurança física e sensorial**: Locais com `wheelchair=no` são excluídos via SQL quando o Membro exige acessibilidade motora, e locais com `nivel_ruido=Alto` são excluídos quando a Tolerância Sensorial é `baixo`.
- **Conformidade LGPD por design**: O banco de dados nunca armazena histórico de solidão, vulnerabilidade psicológica ou transcrições brutas de áudio/texto dos Membros.

