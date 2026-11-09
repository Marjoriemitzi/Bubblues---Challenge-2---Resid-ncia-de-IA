# Bubbles — Challenge 2 (Residência em IA)

> **"Como ajudar pessoas a criar vínculos significativos por meio de encontros presenciais de forma segura?"**  
> *Grupo 10 — TIC-IA / Residência em Inteligência Artificial*

---

## 📌 Visão Geral do Projeto

O **Bubbles** é uma plataforma inteligente projetada para combater a solidão e o isolamento social entre adultos e idosos. O sistema conecta pessoas desconhecidas com alta compatibilidade psicossocial, viabilizando encontros presenciais em pequenos grupos de **3 a 8 pessoas** em locais públicos e comerciais seguros e verificados da comunidade (como cafés tranquilos, centros culturais, livrarias e parques urbanos).

A solução elimina a sobrecarga cognitiva e as barreiras logísticas de marcar encontros:

- **Interpretação de Intenção e "Vibe":** Modelos de Linguagem (LLMs) interpretam solicitações em linguagem natural livre (ex.: *"quero um café calmo para conversar sobre livros"*), extraindo preferências, necessidades psicossociais e restrições de horários e acessibilidade sem a exigência de formulários cansativos.
- **Recomendação e Ranqueamento Híbrido:** Combina busca vetorial semântica (`pgvector`) com filtros geoespaciais em tempo real (`PostGIS`), aplicando uma fórmula de score ponderado por afinidade temática, proximidade física, perfil dos usuários e reputação comunitária ($0.4 \times \text{Google} + 0.6 \times \text{Usuários do App}$).
- **Segurança e Espaços Públicos Verificados:** Todas as recomendações são ancoradas em dados reais de estabelecimentos ativos e verificados (OpenStreetMap / PostGIS), com guardrails ativos de abstenção correta para consultas inviáveis ou fora do escopo social.

---

## 👥 Integrantes da Equipe

| Foto | Nome | GitHub |
| :---: | :--- | :--- |
| <img src="https://github.com/Marjoriemitzi.png" width="60" height="60" style="border-radius: 50%;" alt="Marjorie Mitzi" /> | **Marjorie Mitzi** | [@Marjoriemitzi](https://github.com/Marjoriemitzi) |
| <img src="https://github.com/Ruan-Carvalho.png" width="60" height="60" style="border-radius: 50%;" alt="Ruan Carvalho" /> | **Ruan Carvalho** | [@Ruan-Carvalho](https://github.com/Ruan-Carvalho) |
| <img src="https://github.com/sammiess2.png" width="60" height="60" style="border-radius: 50%;" alt="Samara" /> | **Samara** | [@sammiess2](https://github.com/sammiess2) |
| <img src="https://github.com/yanrdgs-dev.png" width="60" height="60" style="border-radius: 50%;" alt="Yan Santos" /> | **Yan Santos** | [@yanrdgs-dev](https://github.com/yanrdgs-dev) |
