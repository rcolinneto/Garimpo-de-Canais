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
