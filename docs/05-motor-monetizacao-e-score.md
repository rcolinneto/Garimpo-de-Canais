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
