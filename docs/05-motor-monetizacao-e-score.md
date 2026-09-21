# 05 — Motor de Detecção de Monetização e Score de Nicho Viral

Este é o componente de inteligência do sistema. Ele roda depois de cada snapshot.

## Parte 1 — Detecção de sinais de monetização

Não existe API que devolva "monetizado: sim/não" ou o valor real faturado por um canal de terceiros — nenhuma ferramenta de mercado tem esse dado, porque é informação privada do criador/plataforma. O que o sistema pode fazer, e é o que este motor faz, é **inferir monetização por evidência indireta**, sempre guardando a evidência (`monetization_signals.evidence`) para o chefe poder conferir manualmente antes de tomar qualquer decisão baseada nisso.

### Fontes de texto analisadas
- Descrição do canal.
- Descrição dos últimos N vídeos.
- Comentário fixado (quando acessível).

### Taxonomia de sinais (`signal_type`)

| Tipo | O que procura | Exemplos de evidência |
|---|---|---|
| `link_agregador` | Linktree, Beacons, Bio.link, Koji, Stan Store | domínio da URL |
| `link_afiliado` | Parâmetros de afiliado conhecidos (Amazon Associates `tag=`, Shopee, Awin, Lomadee, Hotmart `hotmart.com`, Eduzz, Monetizze, Kiwify) | URL completa |
| `infoproduto` | Palavras-chave como "curso", "mentoria", "e-book", "aulas", "workshop", "imersão" próximas de um link | trecho de texto |
| `loja_propria` | Link para Shopify, Nuvemshop, loja integrada, ou domínio próprio com padrão de e-commerce | URL |
| `patrocinio_mencionado` | "publi", "parceria paga", "#ad", "#publi", "patrocinado por" | trecho de texto |
| `comunidade_paga` | Discord/Telegram/WhatsApp pago, "assinatura", "clube", Patreon/Padrim/Apoia.se | URL ou trecho |
| `elegivel_parceria_plataforma` | Canal já atingiu os requisitos públicos mínimos do YouTube Partner Program (limiares de inscritos/horas assistidas) — isso é público e verificável, diferente do valor faturado | contagem de inscritos/horas |

Implementação: lista de regras (regex + lista de domínios conhecidos) em vez de um modelo de ML — mais barato, mais explicável ao chefe, mais fácil de a Claude Code manter e você adicionar novas regras conforme observar novos padrões. Cada regra tem um `confidence` fixo (ex.: link de afiliado direto = 0.9; palavra "curso" sem link junto = 0.4) gravado em `monetization_signals.confidence`.

### Estimativa de receita (opcional, deixar claramente marcada como estimativa)

Se o chefe quiser uma "régua" de receita e não só sinais binários, é possível estimar uma faixa a partir de `views recentes × um RPM (receita por mil views) configurável por nicho`. Isso é **uma projeção baseada em premissas que você define**, nunca um dado real — o sistema não tem, e nenhuma ferramenta de mercado tem, acesso à receita real de um canal de terceiros. Implementar como:

```
receita_estimada_min = views_ultimos_30_dias / 1000 * rpm_min_do_nicho
receita_estimada_max = views_ultimos_30_dias / 1000 * rpm_max_do_nicho
```

Com `rpm_min_do_nicho`/`rpm_max_do_nicho` configuráveis em `config/niches.yaml` por nicho (nichos como finanças/negócios tipicamente têm RPM mais alto que entretenimento genérico, mas os valores exatos variam por período, região de audiência e formato — devem ser calibrados por vocês, não hardcoded como verdade absoluta). O dashboard deve sempre exibir isso como **faixa estimada**, nunca como número único, e com um texto deixando claro que é uma projeção.

## Parte 2 — Score de nicho viral

Objetivo: um número único para ordenar "o que olhar primeiro", combinando três componentes (gravados separadamente em `channel_scores` para explicabilidade):

### Growth score (crescimento do canal)
Baseado na taxa de crescimento de inscritos e de views entre snapshots (ver `04-coleta-youtube.md`), normalizada — por exemplo, um canal pequeno que dobrou de tamanho em uma semana pontua mais alto que um canal grande que cresceu 5% no mesmo período, porque o objetivo é achar tendências emergentes, não canais já consolidados.

Sugestão de fórmula inicial (ajustável):
```
growth_score = min(100, (taxa_crescimento_inscritos_7d * 100) * fator_tamanho)
```
onde `fator_tamanho` penaliza levemente canais muito grandes (ex.: acima de 500 mil inscritos), já que o objetivo é achar quem está emergindo, não quem já emergiu.

### Monetization score
Soma ponderada dos sinais de monetização detectados recentemente, usando o `confidence` de cada um:
```
monetization_score = min(100, soma(confidence de cada sinal ativo nos últimos 30 dias) * peso_por_tipo)
```
Sinais mais fortes (`link_afiliado`, `loja_propria`) pesam mais que sinais fracos (`patrocinio_mencionado` sem link).

### Niche virality score
Mede se o **nicho como um todo** está bombando, não só um canal isolado — um nicho onde vários canais diferentes estão crescendo ao mesmo tempo é mais interessante do que um único canal isolado crescendo (pode ser sorte de um vídeo viral pontual). Calculado agregando o `growth_score` médio de todos os canais ativos daquele `niche_id` nos últimos N dias.

### Score total
```
total_score = (growth_score * peso_crescimento)
            + (monetization_score * peso_monetizacao)
            + (niche_virality_score * peso_nicho)
```
Pesos default sugeridos: `peso_crescimento = 0.5`, `peso_monetizacao = 0.3`, `peso_nicho = 0.2` — configuráveis em `config/settings.py`, para o chefe poder pedir para "dar mais peso pra monetização" sem precisar mexer em código.

`score_breakdown` (jsonb) deve gravar os três componentes e os pesos usados naquele cálculo, para o dashboard poder mostrar "por que este canal está em primeiro lugar" em vez de só o número final.

## Por que heurísticas e não um modelo de ML na v1

Heurísticas são explicáveis (importante quando o resultado embasa decisão de negócio do chefe), não exigem dados de treino que vocês não têm, e são muito mais rápidas de implementar e ajustar via Claude Code. Um modelo de ML pode ser considerado numa fase futura, depois que houver histórico suficiente de canais rotulados manualmente ("esse aqui realmente virou oportunidade boa") para treinar/validar contra algo real.

---

# Camada de oportunidade (Brecha Viral)

> Acrescentado em 2026-09-17 pela rodada `00b-alinhamento-brecha-viral.md`. Tudo acima continua valendo: o score de canal não foi substituído. A diferença é a unidade — aqui o sujeito é o **vídeo**, não o canal.

## Outlier score

Um vídeo Outlier performa muito acima da média do **próprio canal**. A comparação é sempre interna: 270 mil views é pouco para um canal que faz 800 mil e é um evento para um que faz 20 mil. Comparar canais entre si não diz nada sobre o que fez aquele vídeo funcionar.

```
denominador    = max(média dos OUTROS vídeos do canal, OUTLIER_MIN_BASELINE_VIEWS)
outlier_ratio  = view_count / denominador
outlier_score  = min(100, log10(ratio) / log10(OUTLIER_RATIO_TETO) * 100) * recency_weight
```

- A média é a **dos outros vídeos**, nunca incluindo o próprio: senão um vídeo que explodiu infla justamente a referência que deveria julgá-lo, e quanto maior o pico, mais ele se esconde.
- `outlier_ratio = 1` significa "na média do canal": score 0, não é outlier.
- `recency_weight` decai com a idade do vídeo. A metodologia é explícita que recência é sinal ("quanto mais recente + mais views, melhor"): um pico de 3 dias atrás é oportunidade, o mesmo pico de 8 meses atrás é história.

**Duas decisões vieram de validar com dados reais na Fase 7, não do desenho em papel:**

*Piso no denominador* (`OUTLIER_MIN_BASELINE_VIEWS`). Sem ele, o vídeo mais bem colocado de toda a base era um de 4.173 views num canal que faz 380 — "11x a média" que não prova nada sobre o formato. É o mesmo raciocínio do `growth_min_base` no score de crescimento: percentual sobre base minúscula é ruído com aparência de sinal.

*Escala logarítmica* em vez de linear com saturação. Na linear, um vídeo com 1155x a média pontuava igual a um com 11x — ambos estouravam o teto, e só a recência os separava. Com log, 1000x continua valendo mais que 11x, sem valer cem vezes mais.

**Vídeos curtos (Shorts) não entram na mesma média que vídeos longos.** As distribuições de views são incomparáveis, e misturar as duas produz outlier fantasma. Por isso `videos.duration_seconds` existe no modelo.

**Canal inteiro Outlier**: quando a maioria dos vídeos recentes está acima da média e o canal cresce rápido com poucos vídeos publicados, cada título vira fonte de brecha isolada — inclusive temas que o canal tocou uma vez e abandonou. Isso é sinal no nível do canal e reaproveita o `growth_score` que já existe.

## Anatomia do título

Heurísticas no mesmo molde das de monetização: padrão reconhecido, **evidência anexada** (o trecho exato do título) e confiança. Gravadas em `title_signals`.

| `signal_type` | O que procura | Exemplo de evidência |
|---|---|---|
| `numero_alto` | Número que quantifica a promessa, acima de um limiar configurável | "25" em *"25 esconderijos…"* |
| `autoridade_emprestada` | Profissão/instituição que empresta credibilidade | "policiais aposentados" |
| `gatilho_medo` | Vocabulário de risco, perda, erro | "nunca verificam" |
| `gatilho_desejo` | Ganho, economia, melhora | "economize", "dobre" |
| `gatilho_curiosidade` | Informação retida, segredo, revelação | "ninguém te conta" |
| `promessa_negativa` | Formulação por negação, que costuma performar acima da afirmativa | "não faça", "pare de" |

Cada lista de vocabulário é configurável, pelo mesmo motivo das regras de monetização: gíria e formato mudam, e o chefe precisa poder ajustar sem mexer em código (ver cadência em `10-validacao-e-ajustes.md`).

**Fora daqui de propósito:** "objeto concreto" é peça da metodologia mas não vira heurística — distinguir concreto de abstrato exige compreensão semântica, e uma regra por lista de palavras erraria tanto que o sinal perderia valor. Fica como leitura humana.

## Opportunity score

Combina o que já foi medido, sem inventar dado novo:

```
opportunity_score = (outlier_score        * peso_outlier)
                  + (rpm_normalizado      * peso_rpm)
                  + (espaco_livre_score   * peso_concorrencia)
```

- `rpm_normalizado` vem de `markets.rpm_estimado`, ponderado por `falantes_estimados` — CPM alto com pouco alcance pode render menos que o contrário. É a pergunta 3 das 4.
- `espaco_livre_score` responde à pergunta 2: quanto mais os resultados daquele assunto naquele idioma forem **antigos ou de canais pequenos**, maior o espaço. Sem resultado nenhum não é nota máxima — pode significar que não há demanda (pergunta 1), não que a brecha é livre.
- Pesos configuráveis, como os do score de canal.

A pergunta 4 ("o assunto faz sentido nesse país?") **não entra na fórmula**. Clima, hábito e cultura não são deriváveis das métricas que temos, e fingir que são transformaria um palpite em número com aparência de precisão. Ela aparece no dashboard como checagem manual pendente, em `opportunities.notes`.

## Por que a monetização continua importando

Ela muda de papel em vez de sair: os sinais de monetização detectados no canal de origem são a prova concreta de que aquele nicho **paga** — sustentação de mercado para a pergunta do RPM, vinda de evidência observada e não de tabela estimada.
