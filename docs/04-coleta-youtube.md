# 04 — Módulo de Coleta: YouTube

Este é o núcleo do sistema: toda a coleta de dados usa a **YouTube Data API v3** (API oficial, gratuita, estável e documentada).

## O limite que rege todo o desenho deste módulo: cota da API

- Cada projeto no Google Cloud recebe **10.000 unidades por dia**, resetando à meia-noite (horário do Pacífico, EUA).
- `search.list` (o endpoint de busca por palavra-chave) custa **100 unidades por chamada** — ou seja, na prática, dá para fazer no máximo ~100 buscas por dia com uma única chave de API, e isso teria que ser o único uso da cota do dia.
- `channels.list` e `videos.list` (endpoints de "me dá os dados de um canal/vídeo que eu já sei o ID") custam **1 unidade por chamada** — muitíssimo mais baratos.
- Não existe compra self-service de mais cota: para aumentar o limite é preciso preencher o formulário de auditoria e extensão de cota do Google, sem prazo garantido de resposta, e pedidos para uso intensivo de dados são frequentemente negados.

Isso define a estratégia obrigatória: **usar `search.list` o mínimo possível, e depender de `channels.list`/`videos.list` para tudo que for reconsulta de algo já conhecido.**

(Fontes: [GetPhyllo — YouTube API Quota Limits 2026](https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota), [SocialCrawl — YouTube Data API 2026](https://www.socialcrawl.dev/blog/youtube-data-api-2026))

## Estratégia de descoberta (job caro, roda pouco)

Combinar duas técnicas para reduzir dependência de `search.list`:

1. **Busca direta por nicho** (`search.list`, `type=channel` ou `type=video`, com as keywords do nicho): usar com parcimônia — por exemplo, rotacionar 5 a 10 nichos por dia em vez de rodar todos os nichos todo dia, para nunca passar de uma fração pequena da cota diária nisso. Cada chamada de `search.list` já retorna até 50 resultados por página, o que normalmente é suficiente para uma varredura por nicho sem precisar paginar muito.
2. **Vídeos em alta por categoria** (`videos.list` com `chart=mostPopular` e `videoCategoryId`), que custa só 1 unidade por chamada: é uma forma barata de encontrar vídeos que estão bombando agora, e a partir do `channelId` desses vídeos, descobrir canais candidatos sem gastar cota de busca. Depois de ter o `channelId`, os dados completos do canal saem por `channels.list` (1 unidade).

Um canal só "entra" na base (`channels` + primeiro `channel_snapshot`) se passar por um filtro mínimo de relevância — por exemplo: menos de N inscritos (é "descoberta", não recadastro do MrBeast) e pelo menos um vídeo recente com views desproporcionais ao tamanho do canal (sinal de crescimento inicial). Esse filtro evita poluir a base com canais grandes e irrelevantes para o objetivo do produto.

## Estratégia de snapshot (job barato, roda todo dia)

Para cada canal já cadastrado: uma chamada `channels.list` (parte `statistics` + `snippet`) por canal, 1 unidade cada. Com 10.000 unidades/dia e reservando uma fatia para descoberta, dá para acompanhar milhares de canais por dia tranquilamente só com isso.

Cálculo de crescimento: comparar o snapshot de hoje com o snapshot de N dias atrás (ex.: 7 dias) para calcular `taxa_crescimento_inscritos = (atual - anterior) / anterior`. Isso é o que alimenta o `growth_score` (ver `05-motor-monetizacao-e-score.md`).

Para `avg_views_last_n_videos` e `engagement_rate`: usar `search.list` com `type=video` **filtrado por `channelId`** custa 100 unidades também — evitar. Alternativa mais barata: usar o endpoint de playlist de uploads do canal (`playlistItems.list`, 1 unidade por chamada, retorna os últimos vídeos) para pegar os `videoId`s recentes, e então `videos.list` (1 unidade, aceita até 50 IDs por chamada) para pegar estatísticas desses vídeos. Isso dá o mesmo resultado por uma fração do custo.

## Dados coletados por canal

- `snippet`: título, descrição, data de criação, thumbnail, país (quando disponível).
- `statistics`: inscritos, total de views, total de vídeos.
- Últimos vídeos (via playlist de uploads + `videos.list`): título, views, curtidas, comentários, data de publicação — usados tanto para `engagement_rate` quanto para o motor de monetização (descrição do vídeo é onde ficam links de afiliado/produto).

## Múltiplas chaves de API

Se o número de canais monitorados crescer e uma única chave (10k unidades/dia) não for suficiente, o Google permite criar múltiplos projetos/chaves (dentro dos termos de uso — não é para burlar limites de forma abusiva, é a forma prevista de escalar um uso legítimo). A arquitetura deve prever um pool de chaves configurável (`config/settings.py`) com rotação simples quando uma chave estiver perto do limite diário, registrando o consumo em `collection_runs.api_units_consumed` (ver `03-modelo-de-dados.md`) para saber quando isso é necessário.

## Erros e casos de borda a tratar

- Canal ficou privado ou foi excluído: `channels.list` retorna vazio — marcar `status = removed` em vez de apagar o histórico.
- Canal desabilitou contagem pública de inscritos: `statistics.hiddenSubscriberCount = true` — tratar `subscriber_count` como nulo naquele snapshot, não como zero.
- Quota estourada no meio do job: o job deve parar de forma limpa, registrar em `collection_runs` quantos itens processou antes de parar, e retomar no próximo dia de onde parou (não do zero).
