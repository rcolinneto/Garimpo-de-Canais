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

## Perguntas em aberto (precisam do chefe antes da implementação final)

1. **Quais mercados/idiomas entram primeiro?** A tabela de RPM e o custo de
   cota dependem dessa lista. Sugestão para começar: 3 a 5 países, misturando
   CPM alto (EUA, Alemanha) com concorrência menor (Polônia, Itália).
2. **Qual o apetite de cota?** Manter 1 chave e reduzir ambição, ou provisionar
   chaves adicionais?
3. **Quem julga "ângulo vago"?** O sistema consegue mostrar evidência (os
   resultados naquele idioma são antigos? de canais pequenos?), mas julgar se
   um recorte é de fato relevante para aquele país é decisão humana — a
   pergunta 4 das 4 não é automatizável com honestidade.

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
