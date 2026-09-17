# 06 — Dashboard Web

Implementado em Streamlit (ver justificativa em `02-arquitetura.md`), lendo dados via a camada FastAPI (não direto do banco, para manter a separação de responsabilidades).

## Tela 1 — Visão Geral / Radar de Nichos

Objetivo: em 10 segundos, o chefe entende "o que está bombando agora".

- Cartões/tabela com os nichos monitorados, ordenados por `niche_virality_score` médio.
- Para cada nicho: número de canais ativos, quantos são "novos esta semana", `niche_virality_score`.
- Gráfico de evolução do `niche_virality_score` do nicho ao longo do tempo (últimos 30/90 dias).

## Tela 2 — Canais Descobertos (tabela principal)

A tela de trabalho principal.

- Tabela com filtros: nicho, faixa de inscritos, taxa de crescimento mínima, sinais de monetização presentes (multi-select pela taxonomia de `05-motor-monetizacao-e-score.md`), score mínimo.
- Ordenação padrão: `total_score` decrescente.
- Colunas: nome do canal (com link direto), nicho, inscritos atuais, crescimento (%) nos últimos 7/30 dias, sinais de monetização (badges), `total_score`, data de descoberta.
- Botão de exportar a visão filtrada atual para CSV.

## Tela 3 — Detalhe do Canal

Ao clicar em um canal na Tela 2:

- Cabeçalho: nome, link, data de descoberta, nicho.
- Gráfico de linha: inscritos e views ao longo do tempo (todos os `channel_snapshots` daquele canal).
- Gráfico de linha secundário: evolução do `total_score` e seus três componentes.
- Lista de sinais de monetização detectados, com a evidência (texto/URL) que motivou cada um — importante para o chefe poder validar manualmente antes de agir.
- Faixa de receita estimada (se o cálculo de RPM estiver habilitado), sempre rotulada como estimativa.
- Últimos vídeos coletados, com views e data.

## Tela 4 — Configuração de Nichos

- CRUD simples sobre a tabela `niches`: adicionar/editar/pausar nicho e suas keywords.
- Isso evita que qualquer mudança de nicho monitorado exija mexer em código ou pedir para você.

## Tela 5 — Alertas e Relatórios

- Configuração do limiar de `total_score` que dispara alerta por e-mail (usa `alerts_sent` para não duplicar notificação).
- Histórico de alertas já enviados.
- Botão de gerar relatório periódico (ex.: resumo semanal em PDF/e-mail) — pode ficar para uma fase posterior se não for prioridade do MVP.

## Autenticação

Uma senha simples compartilhada (Streamlit suporta isso via variável de ambiente + um pequeno gate de login) é suficiente, já que é uso interno de uma pessoa/pequeno time. Login individual com usuários/papéis só se torna necessário se mais pessoas da empresa forem usar o dashboard — nesse caso, é um bom gatilho para migrar a apresentação de Streamlit para FastAPI + React (ver ressalva em `02-arquitetura.md`).

## Tela 6 — Brechas (camada de oportunidade)

> Acrescentada em 2026-09-17 pela rodada `00b-alinhamento-brecha-viral.md`. Entregável da Fase 9.

A entrega final da metodologia Brecha Viral: a lista de oportunidades candidatas, ordenada por `opportunity_score`.

Cada brecha mostra, em uma linha expansível:

- **O vídeo que provou a demanda** — título, canal, views, quantas vezes acima da média do canal (o outlier), e há quantos dias foi publicado. É a condição 1 da metodologia, com o link para conferir no YouTube.
- **As peças do formato reconhecidas** — os `title_signals` com a evidência de cada um, no mesmo formato visual dos sinais de monetização da Tela 3.
- **O ângulo vago identificado** e, quando houver, o **mercado sugerido** com o RPM estimado e o número de falantes.
- **A prova de espaço livre** — os resultados encontrados naquele idioma são antigos? de canais pequenos? É a resposta à pergunta 2 das 4, com os dados que a sustentam.
- **O que falta validar manualmente** — a pergunta 4 ("o assunto faz sentido nesse país?") aparece como pendência explícita, com campo de anotação. O sistema não a responde.

Ações disponíveis: mover o status entre `mapeada`, `validada`, `ocupada` e `descartada`. Só uma pessoa move — o sistema cria como `mapeada` e no máximo sugere `validada`.

**Regra que vale aqui igual às outras telas**: nenhuma brecha aparece sem a evidência que a sustenta. Um número de oportunidade sem a prova ao lado seria um palpite com aparência de dado.
