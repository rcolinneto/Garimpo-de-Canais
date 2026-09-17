# 00b — Rodada de Alinhamento: metodologia Brecha Viral

Segunda rodada de alinhamento do projeto, aberta conforme o processo definido
em `00-brainstorm-e-alinhamento.md` (última linha) e em
`10-validacao-e-ajustes.md` (seção "Processo de ajuste"). Existe porque o
pedido abaixo **não é correção nem calibração: é mudança de escopo**, e o
projeto proíbe mexer no PRD sem registrar a rodada primeiro.

## Pedido

O chefe pediu mudar a metodologia do software para a do mini treinamento
"Brecha Viral", que ele comprou em 2026-09-16. A metodologia está resumida em
`brecha-viral/metodologia.md`.

**Data**: 2026-09-17. **Pedido por**: o chefe (patrocinador). **Registrado
por**: Renato.

## Classificação

**Mudança de escopo.** O sistema atual responde *"quais canais estão crescendo
e monetizando nos nichos que eu configurei"*. A metodologia Brecha Viral
responde *"qual formato já validado eu posso ocupar, com qual ângulo e em qual
mercado, sem disputar com ninguém"*. São perguntas diferentes, e mudam a
unidade de análise:

| | Hoje | Brecha Viral |
|---|---|---|
| Unidade de análise | canal | **vídeo** (e a brecha derivada dele) |
| Sinal principal | crescimento + monetização | **outlier**: vídeo muito acima da média do próprio canal |
| Recorte | nicho configurado | assunto validado × ângulo × **mercado/idioma** |
| Entrega | lista de canais priorizados | lista de **oportunidades** com a prova que as sustenta |

## Decisão: somar, não substituir

A nova metodologia entra como **camada de oportunidade sobre o radar atual**,
que vira sua base de dados. Motivo técnico, não sentimental:

Detectar um vídeo Outlier exige saber a **média histórica de views do canal** —
que é exatamente o que o snapshot diário já constrói. O campo
`channel_snapshots.avg_views_last_n_videos` já é o denominador do cálculo, e o
`raw_payload` já guarda os vídeos recentes com views e data. Substituir o
sistema significaria reconstruir do zero a linha de base que ele já tem.

A detecção de monetização também ganha papel novo em vez de sair de cena: ela
deixa de ser o fim e passa a ser **prova de que o nicho paga** — a evidência
para a pergunta 3 das 4 ("o RPM compensa?"), no nível do nicho.

## O que muda

1. **Vídeos viram entidade de primeira classe.** Hoje existem só dentro do
   `raw_payload`; passam a ter tabela própria, para calcular o outlier e
   acompanhar a evolução de cada um. Ver `03-modelo-de-dados.md`.
2. **Novo score de oportunidade**, ao lado do score de canal: quão acima da
   média o vídeo está, ponderado por quão recente é. Ver
   `05-motor-monetizacao-e-score.md`.
3. **Anatomia do título** vira detecção por heurística, no mesmo molde dos
   sinais de monetização (padrão + evidência + confiança): número alto,
   autoridade emprestada, gatilho de medo/desejo/curiosidade.
4. **Mercado/idioma vira dimensão do sistema**, com tabela de referência de RPM
   por país.
5. **Brecha vira entidade** com ciclo de vida: mapeada → validada → ocupada →
   descartada.

## O que **não** muda

- A regra arquitetural de `02-arquitetura.md`: o dashboard nunca fala com o
  banco direto.
- O princípio de `01`: o sistema **estima e mostra a evidência**, nunca afirma
  o que não pode provar. Vale igual para brecha: ele aponta candidatas com a
  prova, não decreta que uma brecha existe.
- A coleta segue na YouTube Data API v3 oficial, dentro dos Termos de Uso.
- Nichos continuam cadastrados manualmente pelo chefe.

## Achado técnico: não vamos usar proxy nem spoofing

A Aula 3 menciona uma "ferramenta de mineração" com proxy e spoofing de
localização para ver o YouTube de outros países. **Nosso caminho não precisa
disso.** A YouTube Data API aceita `regionCode` e `relevanceLanguage` como
parâmetros nativos de `search.list` e `videos.list` — pedir dados de outro país
é um campo na requisição, não uma fraude de geolocalização.

Isso importa por três motivos: é mais barato (sem infra de proxy), é mais
confiável (dado oficial, não página renderizada) e mantém o sistema dentro dos
Termos de Uso — coerente com a decisão já registrada em `00` de não basear o
produto em scraping que viole ToS.

## Restrição dura: cota da API

Esta é a maior ameaça ao pedido, e precisa de decisão do chefe.

- `search.list` custa **100 unidades**; a cota diária da chave é **10.000**.
- Validar uma brecha em 5 mercados por busca = 5 × 100 = **500 unidades**, ou
  5% da cota do dia para **uma única** brecha.
- **A cota já está estourando hoje**, antes da nova metodologia: em 2026-09-14 a
  busca sob demanda respondeu "cota do dia estourou" tendo gasto 100 unidades e
  achado zero canais.

Mitigação desenhada: `videos.list` com `chart=mostPopular&regionCode=XX` custa
**1 unidade** — cem vezes menos que uma busca. Dá para varrer o que está em alta
em vários países de forma barata e reservar o `search.list` só para confirmar
uma brecha específica, com orçamento por execução (o mecanismo de
`discovery_quota_budget` já existe).

Mesmo assim, operar em N mercados multiplica o consumo. As saídas são: mais
chaves de API (o coletor já rotaciona chaves), menos mercados por ciclo, ou
ciclos mais espaçados. **Decisão pendente do chefe.**

## Decisões (fechadas em 2026-09-17)

**1. Mercados: carteira mista, 4 países.** Um de CPM alto e três de menor
concorrência, para comparar na prática qual rende mais antes de concentrar
esforço:

| Mercado | `regionCode` | `relevanceLanguage` | Papel |
|---|---|---|---|
| Estados Unidos | `US` | `en` | Maior CPM e alcance; maior concorrência |
| Alemanha | `DE` | `de` | CPM alto com concorrência menor |
| Itália | `IT` | `it` | Concorrência baixa |
| Polônia | `PL` | `pl` | Concorrência baixa, CPM ainda relevante |

**2. Cota: uma chave só, com rodízio de mercados.** Não provisionar chaves
novas por ora. Cada execução valida **um** mercado, em rodízio — com 4 mercados
cadastrados, cada um é revisitado a cada 4 ciclos.

A decisão é coerente com a metodologia: brecha não surge e desaparece em 24
horas, então revisitar um mercado a cada poucos dias não perde oportunidade. E
é o que cabe em 10.000 unidades diárias enquanto a descoberta por nicho e o
snapshot continuam rodando na mesma cota.

Consequência a respeitar na implementação: `markets` precisa de controle de
"último ciclo em que foi validado", igual ao `niches.last_discovery_at` que já
existe para o rodízio de nichos.

**3. Julgamento humano: o chefe decide direto.** Não haverá curadoria prévia —
todas as candidatas aparecem para ele, cada uma com a prova ao lado, e é ele
quem move entre `mapeada`, `validada`, `ocupada` e `descartada`.

Isso **aumenta a exigência sobre a ordenação**: sem filtro humano antes, o
`opportunity_score` é o que separa o que ele olha primeiro do que ele nunca vai
rolar a página para ver. Uma candidata fraca no topo custa a confiança dele na
tela inteira. Duas implicações práticas, registradas para a Fase 9:

- A Tela 6 nasce ordenada por score e com corte configurável, não como lista
  crua.
- Vale mostrar quantas candidatas foram geradas e quantas ficaram abaixo do
  corte — esconder ruído sem dizer que existe é enganoso.

## Ainda em aberto

- **Revisão do RPM estimado.** Os valores de `markets.rpm_estimado` são
  estimativa de mercado, não dado da API. Precisam de uma primeira calibragem
  com o chefe e de revisão periódica (cadência em `10-validacao-e-ajustes.md`).
- **Limiar de corte da Tela 6.** Só dá para definir com candidatas reais na
  tela; fica para a validação da Fase 9.

## Limites de honestidade do sistema

Registrados aqui para não virarem promessa implícita:

- O sistema **não decide** que uma brecha é boa. Ele ordena candidatas por
  evidência e mostra o porquê, como já faz com monetização.
- "Objeto concreto" na anatomia do título não é detectável por heurística
  simples com qualidade aceitável — fica como leitura humana, não como sinal
  automático.
- RPM por país é **estimativa de mercado**, não dado da API. Vem de tabela
  curada manualmente e precisa de revisão periódica, igual às regras de
  monetização (ver cadência em `10-validacao-e-ajustes.md`).

## Impacto no roadmap

Novas fases entram em `08-roadmap-de-fases.md` depois da Fase 6, sem reabrir as
fases já concluídas — o que existe continua funcionando enquanto a camada nova
é construída em cima.
