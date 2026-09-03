# 08 — Roadmap de Fases para Construção com Claude Code

Cada fase abaixo foi desenhada para ser uma sessão de trabalho independente com o Claude Code, dentro da pasta do projeto (que já tem `CLAUDE.md` na raiz apontando para toda essa documentação). Trabalhe em ordem — cada fase assume que a anterior está pronta e commitada. Revise o que foi gerado (rode, leia o diff) antes de avançar.

Cada fase traz: objetivo, entregáveis esperados, e um prompt pronto para colar no Claude Code (adapte o que estiver entre colchetes).

---

## Fase 0 — Setup do projeto

**Objetivo**: esqueleto do repositório, ambiente reprodutível, sem lógica de negócio ainda.

**Entregáveis**: estrutura de pastas de `02-arquitetura.md`, `pyproject.toml` com dependências (fastapi, sqlalchemy, alembic, apscheduler, streamlit, google-api-python-client, pydantic, python-dotenv, pytest), `Dockerfile` e `docker-compose.yml` funcionais (sobe app + Postgres), `.env.example`.

**Prompt sugerido**:
> Leia `docs/02-arquitetura.md`. Crie o esqueleto do projeto Python seguindo exatamente a estrutura de pastas descrita lá. Configure `pyproject.toml` com as dependências necessárias (fastapi, uvicorn, sqlalchemy, alembic, apscheduler, streamlit, google-api-python-client, pydantic, pydantic-settings, python-dotenv, psycopg2-binary, pytest). Crie um `Dockerfile` e `docker-compose.yml` que suba a aplicação e um PostgreSQL, com um `.env.example` documentando todas as variáveis necessárias. Ainda não implemente lógica de negócio — só o esqueleto rodando (um endpoint `/health` no FastAPI é suficiente para validar que subiu).

---

## Fase 1 — Modelo de dados e banco

**Objetivo**: schema completo funcionando com migrations.

**Entregáveis**: modelos SQLAlchemy para todas as tabelas de `03-modelo-de-dados.md`, migration inicial via Alembic, seed script opcional para popular alguns `niches` de exemplo.

**Prompt sugerido**:
> Leia `docs/03-modelo-de-dados.md`. Implemente os modelos SQLAlchemy correspondentes em `src/db/models.py`, configure o Alembic e gere a migration inicial criando todas essas tabelas com os relacionamentos e índices descritos. Crie um script de seed que insira 2-3 nichos de exemplo em `niches` para facilitar testes manuais.

---

## Fase 2 — Coletor YouTube (núcleo do sistema)

**Objetivo**: o sistema já descobre e acompanha canais reais do YouTube.

**Entregáveis**: `collectors/models.py` com os modelos comuns (`ChannelRef`, `ChannelSnapshot`, `ContentSignal`), `collectors/youtube.py` implementando `discover_candidates`, `fetch_snapshot` e `fetch_recent_content_signals` conforme `04-coleta-youtube.md`, jobs de descoberta e snapshot agendados via APScheduler gravando em `collection_runs`.

**Prompt sugerido**:
> Leia `docs/02-arquitetura.md` (seção do collector) e `docs/04-coleta-youtube.md`. Implemente `src/collectors/models.py` com os modelos de dados comuns e `src/collectors/youtube.py` com os três métodos usando a YouTube Data API v3 (biblioteca `google-api-python-client`), respeitando exatamente a estratégia de economia de cota descrita no documento (usar `search.list` só para descoberta, `channels.list`/`videos.list`/`playlistItems.list` para tudo que for reconsulta). Implemente também os dois jobs (descoberta e snapshot) agendados via APScheduler, gravando cada execução na tabela `collection_runs` incluindo `api_units_consumed`. Trate os casos de borda descritos no fim do documento (canal removido, inscritos ocultos, cota estourada no meio do job).

---

## Fase 3 — Motor de monetização e score

**Objetivo**: cada snapshot novo gera sinais de monetização e um score.

**Entregáveis**: `enrichment/monetization.py` com as regras de `05-motor-monetizacao-e-score.md`, `enrichment/scoring.py` com o cálculo dos três componentes e do score total, disparado automaticamente após cada job de snapshot.

**Prompt sugerido**:
> Leia `docs/05-motor-monetizacao-e-score.md`. Implemente `src/enrichment/monetization.py` com as regras de detecção descritas na taxonomia (regex/lista de domínios, gravando em `monetization_signals` com `signal_type`, `evidence` e `confidence`), e `src/enrichment/scoring.py` calculando `growth_score`, `monetization_score`, `niche_virality_score` e `total_score` conforme as fórmulas do documento, com os pesos configuráveis em `src/config/settings.py`. Esse enriquecimento deve rodar automaticamente logo após cada execução do job de snapshot da Fase 2, gravando o resultado em `channel_scores`.

---

## Fase 4 — API interna (FastAPI)

**Objetivo**: endpoints de leitura que o dashboard vai consumir.

**Entregáveis**: `api/main.py` com endpoints como `GET /canais` (com os filtros de `06-dashboard.md`), `GET /canais/{id}`, `GET /canais/{id}/historico`, `GET /nichos/ranking`, `GET /health`.

**Prompt sugerido**:
> Leia `docs/06-dashboard.md` para entender que filtros e visualizações o dashboard vai precisar, e `docs/03-modelo-de-dados.md` para o schema. Implemente em `src/api/main.py` os endpoints FastAPI necessários para servir essas telas (listagem de canais com os filtros descritos, detalhe de canal com histórico de snapshots e scores, ranking de nichos). Inclua testes básicos com pytest para cada endpoint.

---

## Fase 5 — Dashboard (Streamlit)

**Objetivo**: interface visual completa para o chefe usar.

**Entregáveis**: as 5 telas descritas em `06-dashboard.md`, consumindo a API da Fase 4, com autenticação simples por senha.

**Prompt sugerido**:
> Leia `docs/06-dashboard.md` na íntegra. Implemente o dashboard em `src/dashboard/app.py` (Streamlit, com múltiplas páginas) cobrindo as 5 telas descritas: Visão Geral, Canais Descobertos (com todos os filtros listados), Detalhe do Canal (com os gráficos de evolução), Configuração de Nichos (CRUD simples) e Alertas/Relatórios. Consuma os dados via os endpoints da API implementados na fase anterior, não direto do banco. Implemente a autenticação simples por senha compartilhada via variável de ambiente.

---

## Fase 6 — Alertas e exportação

**Objetivo**: o sistema avisa proativamente, sem depender de alguém abrir o dashboard.

**Entregáveis**: job que verifica canais que cruzaram o limiar de score configurado, envia e-mail, registra em `alerts_sent` para não duplicar; exportação da tabela de canais para CSV a partir do dashboard.

**Prompt sugerido**:
> Leia a seção "Tela 5" de `docs/06-dashboard.md` e a tabela `alerts_sent` de `docs/03-modelo-de-dados.md`. Implemente um job agendado que, após cada cálculo de score (Fase 3), verifica quais canais cruzaram o limiar configurado e ainda não tiveram alerta enviado para esse evento, envia um e-mail simples (via SMTP configurado em variáveis de ambiente) e registra em `alerts_sent`. Adicione também o botão de exportação para CSV na Tela 2 do dashboard.

---

## Depois de tudo pronto

Volte para `README.md` e reveja o "Resumo para quem vai apresentar isso ao chefe" — nesse ponto você já vai ter dados reais do sistema (quantos canais descobertos, que nichos estão pontuando mais alto) para mostrar o valor entregue.
