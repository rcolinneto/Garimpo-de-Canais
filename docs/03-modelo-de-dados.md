# 03 — Modelo de Dados

> **Revisado em 2026-09-17** pela rodada `00b-alinhamento-brecha-viral.md`. As tabelas originais continuam como estão; as novas (`videos`, `video_snapshots`, `title_signals`, `markets`, `opportunities`) sustentam a camada de oportunidade.

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
| last_discovery_at | timestamptz | nullable — sustenta o rodízio entre nichos, já que `search.list` custa 100 unidades e não dá para rodar todos os nichos todo dia |

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

## `videos`
Um vídeo de um canal monitorado. Até 2026-09-17 os vídeos existiam só dentro de `channel_snapshots.raw_payload`; viraram tabela própria porque o outlier é calculado **por vídeo**, e porque um vídeo precisa ser acompanhado ao longo do tempo (views crescem).

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| channel_id | FK → channels | |
| youtube_video_id | text unique | ID nativo do vídeo |
| title | text | matéria-prima da anatomia do título |
| published_at | timestamptz | idade do vídeo pondera o outlier: recente vale mais |
| duration_seconds | integer | nullable — separa short de vídeo longo, que têm médias incomparáveis |
| first_seen_at | timestamptz | quando o sistema viu o vídeo pela primeira vez |

Índice em `(channel_id, published_at)`.

## `video_snapshots`
Métricas de um vídeo ao longo do tempo. Mesma lógica de `channel_snapshots`: sem série temporal não dá para dizer se um vídeo *está* acelerando ou só é antigo e acumulou views.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| video_id | FK → videos | |
| collected_at | timestamptz | |
| view_count | bigint | |
| like_count | bigint | nullable — canal pode ocultar |
| comment_count | bigint | nullable |

Índice em `(video_id, collected_at)`.

## `video_outliers`
O resultado do cálculo de outlier, por vídeo e por execução do motor. Tabela separada (e não coluna em `videos`) pelo mesmo motivo de `channel_scores`: o outlier muda conforme o canal e o vídeo evoluem, e ver essa evolução importa.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| video_id | FK → videos | |
| calculated_at | timestamptz | |
| baseline_views | numeric | média do canal usada como denominador, guardada para explicabilidade |
| outlier_ratio | numeric | views ÷ baseline — "quantas vezes acima da média do próprio canal" |
| recency_weight | numeric | peso pela idade do vídeo |
| outlier_score | numeric | valor final usado para ordenar |
| breakdown | jsonb | as partes do cálculo, para o dashboard explicar o número |

## `title_signals`
Peças reconhecidas na anatomia do título, no mesmo molde de `monetization_signals`: padrão + evidência + confiança. Várias linhas por vídeo.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| video_id | FK → videos | |
| detected_at | timestamptz | |
| signal_type | text | `numero_alto`, `autoridade_emprestada`, `gatilho_medo`, `gatilho_desejo`, `gatilho_curiosidade`, `promessa_negativa` — taxonomia em `05-motor-monetizacao-e-score.md` |
| evidence | text | o trecho exato do título que disparou a detecção |
| confidence | numeric | 0 a 1 |

> "Objeto concreto" existe na metodologia mas **não** vira `signal_type`: não é detectável por heurística simples com qualidade aceitável (ver limites em `00b`). Fica como leitura humana no dashboard.

## `markets`
Países/idiomas candidatos a receber um formato validado. Cadastrado e mantido manualmente — RPM não vem da API.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| region_code | text | ISO 3166-1 alfa-2, o mesmo valor aceito por `regionCode` na API |
| language_code | text | o mesmo valor aceito por `relevanceLanguage` |
| name | text | ex.: "Alemanha (alemão)" |
| rpm_estimado | numeric | **estimativa de mercado**, não dado da API — revisar periodicamente |
| falantes_estimados | bigint | contrapeso do RPM: CPM alto com pouco alcance pode render menos |
| active | boolean | permite pausar um mercado sem perder histórico |
| last_validated_at | timestamptz | nullable — sustenta o rodízio de mercados por ciclo, mesmo papel de `niches.last_discovery_at` |

Carteira inicial decidida em `00b` (mista, 4 países): `US`/`en`, `DE`/`de`, `IT`/`it`, `PL`/`pl`. Com uma chave de API só, cada ciclo valida **um** mercado, em rodízio — o mais antigo em `last_validated_at` primeiro.

## `opportunities`
A brecha em si: o cruzamento de um formato validado com um ângulo e um mercado. É a entrega final da camada nova.

| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| video_id | FK → videos | o vídeo que provou a demanda (condição 1 da metodologia) |
| market_id | FK → markets, nullable | nulo = brecha só de ângulo, mesmo mercado do original |
| angulo | text | o recorte vago identificado (condição 2) |
| status | text | `mapeada`, `validada`, `ocupada`, `descartada` |
| volume_evidence | jsonb | resposta à pergunta 1 das 4: há busca por esse assunto nesse idioma |
| concorrencia_evidence | jsonb | resposta à pergunta 2: resultados são antigos/de canais pequenos |
| opportunity_score | numeric | combinação de outlier + RPM + baixa concorrência |
| created_at | timestamptz | |
| notes | text | julgamento humano (pergunta 4 das 4 não é automatizável) |

> `status` é ciclo de vida, não cálculo: quem move para `ocupada` ou `descartada` é uma pessoa. O sistema só cria como `mapeada` e sugere `validada`.

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

channels  1---N videos              <- camada de oportunidade
videos    1---N video_snapshots
videos    1---N video_outliers
videos    1---N title_signals
videos    1---N opportunities
markets   1---N opportunities
```
