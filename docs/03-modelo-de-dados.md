# 03 — Modelo de Dados

Banco: PostgreSQL. Todas as tabelas usam `id` como chave primária (serial é suficiente para o volume esperado). Os nomes abaixo são sugestões; o importante é a Claude Code manter esses nomes consistentes com os documentos de coleta e score.

## `niches`
Nichos/temas configurados para monitoramento (o chefe cadastra/edita isso).

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| name | text | ex.: "finanças pessoais", "pets exóticos" |
| keywords | text[] | palavras-chave usadas na busca/descoberta |
| active | boolean | permite pausar um nicho sem apagar histórico |
| created_at | timestamptz | |

## `channels`
Um canal do YouTube descoberto pelo sistema.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| youtube_channel_id | text unique | ID nativo do canal na API do YouTube |
| handle | text | @handle do canal |
| display_name | text | |
| niche_id | FK → niches, nullable | nicho em que foi descoberto |
| url | text | link direto para o canal |
| discovered_at | timestamptz | quando entrou no sistema |
| first_seen_subscriber_count | integer | referência para calcular crescimento total desde a descoberta |
| status | text | `active`, `paused`, `removed` (canal saiu do ar/ficou privado) |

> Se um canal fizer sentido em mais de um nicho, criar tabela associativa `channel_niches (channel_id, niche_id)` em vez do campo único acima — deixado como decisão de implementação, sinalizado aqui para não ser esquecido.

## `channel_snapshots`
A tabela mais importante do sistema: uma linha por canal por execução do job de snapshot. É o que sustenta o cálculo de crescimento e os gráficos de evolução.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| channel_id | FK → channels | |
| collected_at | timestamptz | quando o snapshot foi coletado |
| subscriber_count | bigint | nullable (canal pode ocultar contagem de inscritos) |
| total_view_count | bigint | acumulado histórico do canal |
| video_count | integer | |
| avg_views_last_n_videos | numeric | calculado no momento da coleta, ver `04-coleta-youtube.md` |
| engagement_rate | numeric | proxy de engajamento (curtidas+comentários / views das últimas N publicações) |
| raw_payload | jsonb | resposta bruta da API, guardada para auditoria/depuração |

Índice em `(channel_id, collected_at)`.

## `monetization_signals`
Sinais individuais de monetização detectados (várias linhas por canal ao longo do tempo — permite ver quando um canal passou a monetizar).

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| channel_id | FK → channels | |
| detected_at | timestamptz | |
| signal_type | text | `link_agregador`, `link_afiliado`, `infoproduto`, `loja_propria`, `patrocinio_mencionado`, `comunidade_paga`, `elegivel_parceria_plataforma` — taxonomia completa em `05-motor-monetizacao-e-score.md` |
| evidence | text | trecho de texto ou URL que motivou a detecção (para o chefe poder conferir manualmente) |
| confidence | numeric | 0 a 1, ver critérios no doc do motor |

## `channel_scores`
Um score por canal por execução do motor de enriquecimento (série temporal também, para ver a evolução do score, não só o valor atual).

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| channel_id | FK → channels | |
| calculated_at | timestamptz | |
| growth_score | numeric | componente de crescimento |
| monetization_score | numeric | componente de monetização |
| niche_virality_score | numeric | componente de "o nicho como um todo está bombando" |
| total_score | numeric | combinação ponderada final — o campo usado para ordenar o dashboard |
| score_breakdown | jsonb | detalhamento dos pesos aplicados, para explicabilidade |

## `collection_runs`
Log de execução dos jobs (observabilidade — saber se a coleta rodou, quanto tempo levou, se deu erro).

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| job_type | text | `discovery` ou `snapshot` |
| started_at | timestamptz | |
| finished_at | timestamptz | |
| status | text | `success`, `partial`, `failed` |
| items_processed | integer | |
| error_message | text | nullable |
| api_units_consumed | integer | nullable — importante para acompanhar a cota do YouTube |

## `alerts_sent`
Histórico de alertas disparados, para não notificar o mesmo evento duas vezes.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| channel_id | FK → channels | |
| triggered_at | timestamptz | |
| reason | text | ex.: "score cruzou o limiar de 80" |
| channel_out | text | `email`, `dashboard_only` |

## Relação entre as tabelas (resumo)

```
niches    1---N channels
channels  1---N channel_snapshots
channels  1---N monetization_signals
channels  1---N channel_scores
channels  1---N alerts_sent
```
