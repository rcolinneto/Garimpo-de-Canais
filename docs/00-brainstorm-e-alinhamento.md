# 00 — Brainstorm e Alinhamento de Expectativas (Etapa 1)

Este documento registra a etapa de alinhamento que antecedeu o PRD (`01-visao-geral-e-escopo.md`) — o pedido original, as perguntas feitas para reduzir ambiguidade, as opções descartadas e por quê. Serve como referência caso o escopo seja questionado mais adiante ("por que não fizemos X?") e como modelo para futuras rodadas de brainstorm deste mesmo projeto.

## Pedido original

O chefe (na agência onde Renato atua como analista) pediu um software que faça a "mineração" de canais que estão crescendo e monetizando nichos virais — um radar de oportunidades de conteúdo/negócio.

## Partes envolvidas

- **Patrocinador/dono do pedido**: o chefe de Renato — é quem vai consumir o resultado (dashboard) e para quem os critérios de sucesso devem fazer sentido.
- **Executor**: Renato — responsável por especificar, construir (com apoio do Claude Code) e manter o sistema.

## Perguntas de alinhamento e decisões tomadas

| Pergunta | Opções consideradas | Decisão | Justificativa |
|---|---|---|---|
| Quais plataformas minerar? | YouTube apenas / YouTube+TikTok / YouTube+TikTok+Instagram / outra | Inicialmente YouTube+TikTok+Instagram; **revisado para YouTube apenas** após pesquisa técnica | TikTok Research API é restrita a pesquisa acadêmica sem fins lucrativos (não comercial); Instagram Graph API não permite descoberta de contas novas, só consulta de contas já conhecidas. Cobrir as três exigiria provedores de dados pagos de terceiros — decisão de orçamento que o chefe não tinha tomado, então o escopo foi reduzido para não bloquear o início do projeto |
| O que significa "monetizando"? | Sinais indiretos no canal / estimativa de receita / presença de infoprodutos / não sabia ainda | Views + infoprodutos/afiliados, sempre como estimativa/sinal indireto, nunca como dado real | Não existe API ou ferramenta de mercado com acesso à receita real de terceiros — qualquer abordagem "monetização real" seria uma promessa que não pode ser cumprida |
| Stack técnica | Python / Node.js / deixar a cargo do Claude | Python | Preferência explícita do Renato; também é o melhor encaixe para coleta de dados, agendamento e análise |
| Formato de consumo pelo chefe | Dashboard web / relatórios automáticos / dashboard+alertas / CLI | Dashboard web (com alertas por e-mail incluídos na Fase 6) | O chefe precisa explorar/filtrar os achados por conta própria, sem depender de pedir relatório pontual |

## Opções descartadas e por quê (registro para não serem re-propostas sem necessidade)

- **Scraping próprio de TikTok/Instagram**: descartado como base do produto por violar Termos de Serviço das plataformas, risco de bloqueio e risco jurídico/reputacional para a empresa. Pode ser reconsiderado só como decisão explícita do chefe, isolado do restante do sistema.
- **Modelo de Machine Learning para score/monetização na v1**: descartado em favor de heurísticas explicáveis (regras), por não haver dados de treino rotulados disponíveis e por explicabilidade ser mais importante que sofisticação nesta fase — decisão registrada em `05-motor-monetizacao-e-score.md`.
- **Frontend separado (FastAPI + React) na v1**: descartado em favor de Streamlit, para priorizar velocidade de entrega mantendo tudo em Python — a arquitetura isola essa decisão para poder ser revertida depois sem grande retrabalho (ver `02-arquitetura.md`).

## Resultado desta etapa

Escopo fechado documentado em `01-visao-geral-e-escopo.md`, já refletindo as decisões acima. Qualquer mudança de escopo relevante depois da aprovação inicial deve ser registrada como um novo ciclo de alinhamento (uma seção adicional neste documento ou um novo documento `00b-...`), não como edição silenciosa do PRD.
