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

## Fases da camada de oportunidade (Brecha Viral)

> Acrescentadas em 2026-09-17 pela rodada `00b-alinhamento-brecha-viral.md`. Entram **depois** da Fase 6, sem reabrir as anteriores: o radar continua rodando enquanto a camada nova é construída em cima dele.
>
> **Atenção antes da Fase 9**: a cota da API já estoura hoje (ver aviso em `04-coleta-youtube.md`). A decisão de `00b` foi manter **uma única chave** e rodar **um mercado por ciclo**, em rodízio — o desenho precisa caber nessa restrição, não contorná-la.

### Fase 7 — Vídeos como entidade e detecção de outlier ✅ concluída em 2026-09-21

**Objetivo**: responder "que vídeo performou muito acima da média do próprio canal", que é o passo GARIMPAR da metodologia.

**Entregáveis**: tabelas `videos`, `video_snapshots` e `video_outliers`; migration; extração dos vídeos que já estão em `channel_snapshots.raw_payload` (o histórico já coletado não se perde); cálculo do outlier ponderado por recência, com Shorts separados de vídeos longos; nova seção na Tela 3 listando os outliers do canal com o porquê do número.

**Resultado**: 845 vídeos e 844 outliers recuperados do histórico **sem gastar uma unidade de cota** — tudo já estava em `channel_snapshots.raw_payload`. Dos 71 canais, 29 têm outlier relevante. A calibragem foi ajustada durante a validação (piso no denominador e escala log, ver `05`), depois que a primeira versão colocou um vídeo de 4 mil views em primeiro lugar.

**Prompt sugerido**:
> Leia a seção "Camada de oportunidade" de `docs/05-motor-monetizacao-e-score.md` e as tabelas `videos`, `video_snapshots` e `video_outliers` de `docs/03-modelo-de-dados.md`. Implemente a coleta por vídeo e o cálculo de outlier_score. Aproveite o que já existe: `channel_snapshots.avg_views_last_n_videos` é a linha de base, e `raw_payload.recent_videos` já tem os vídeos históricos. Use `videos.list` em lote (até 50 IDs por unidade de cota).

### Fase 8 — Anatomia do título ✅ concluída em 2026-09-21

**Objetivo**: o passo DISSECAR — quebrar o formato do vídeo em peças reconhecíveis.

**Entregáveis**: tabela `title_signals`; heurísticas por lista configurável para os seis `signal_type` documentados; exibição das peças reconhecidas com a evidência (o trecho exato do título) na Tela 3.

**Resultado**: 374 peças reconhecidas em 334 dos 845 vídeos, sem custo de cota (o título já estava no banco). Distribuição: curiosidade 101, desejo 95, número alto 93, medo 52, promessa negativa 29, autoridade emprestada 4. Dois falsos positivos de `numero_alto` foram encontrados validando com dados reais e corrigidos — valor em dinheiro e medida de tempo — o que removeu 27 detecções erradas.

**Prompt sugerido**:
> Leia "Anatomia do título" em `docs/05-motor-monetizacao-e-score.md`. Implemente a detecção no mesmo molde de `src/enrichment/monetization.py`: padrão, evidência anexada e confiança. Lembre que "objeto concreto" foi deliberadamente deixado de fora — não invente heurística para ele.

### Fase 9 — Mercados e brechas

**Objetivo**: os passos MAPEAR e VALIDAR — onde esse formato ainda não tem dono.

**Entregáveis**: tabelas `markets` (semeada com a carteira de `00b`: US/en, DE/de, IT/it, PL/pl) e `opportunities`; **rodízio de um mercado por ciclo** via `last_validated_at`; varredura barata por país com `chart=mostPopular&regionCode=XX` (1 unidade); `search.list` só para confirmar uma brecha específica, sob orçamento de cota; `opportunity_score`; **Tela 6 — Brechas**, ordenada por score com corte configurável, a prova de cada candidata e o campo de anotação manual.

**Prompt sugerido**:
> Leia "Coleta para a camada de oportunidade" em `docs/04-coleta-youtube.md` e "Opportunity score" em `docs/05-motor-monetizacao-e-score.md`. Respeite a estratégia de custo: varredura barata primeiro, `search.list` só no fim. A 4ª das "4 perguntas" não entra na fórmula — ela é campo de anotação manual.

---

## Depois de tudo pronto

Volte para `README.md` e reveja o "Resumo para quem vai apresentar isso ao chefe" — nesse ponto você já vai ter dados reais do sistema (quantos canais descobertos, que nichos estão pontuando mais alto) para mostrar o valor entregue.
