# Garimpo de Canais (YouTube) — Documentação de Projeto

Sistema para descobrir automaticamente canais do YouTube em crescimento acelerado que estão monetizando nichos virais, com um dashboard web para acompanhamento.

Este repositório contém a especificação completa do projeto (em `docs/`) e a implementação, construída fase a fase com o **Claude Code**. As 7 fases do roadmap estão concluídas: coleta, motor de score, API, dashboard e alertas.

## Como usar esta documentação com o Claude Code

1. Extraia esta pasta (`garimpo-de-canais/`) e inicialize um repositório git dentro dela:
   ```
   cd garimpo-de-canais
   git init
   ```
2. Deixe o arquivo `CLAUDE.md` na raiz do repositório — o Claude Code lê esse arquivo automaticamente ao iniciar uma sessão nesta pasta, e ele referencia todos os documentos em `docs/`.
3. Abra o Claude Code dentro dessa pasta e siga o roadmap em `docs/08-roadmap-de-fases.md`. Cada fase ali tem um prompt pronto para colar — trabalhe **uma fase por vez**, em sessões separadas, revisando o que foi gerado antes de avançar para a próxima.

## Índice dos documentos

| Arquivo | Conteúdo |
|---|---|
| [`docs/00-brainstorm-e-alinhamento.md`](docs/00-brainstorm-e-alinhamento.md) | Etapa 1: pedido original, perguntas de alinhamento, opções descartadas e por quê |
| [`docs/01-visao-geral-e-escopo.md`](docs/01-visao-geral-e-escopo.md) | Objetivo, escopo e critérios de sucesso |
| [`docs/02-arquitetura.md`](docs/02-arquitetura.md) | Arquitetura geral, componentes, stack técnica, diagrama |
| [`docs/03-modelo-de-dados.md`](docs/03-modelo-de-dados.md) | Schema do banco de dados |
| [`docs/04-coleta-youtube.md`](docs/04-coleta-youtube.md) | Módulo de coleta do YouTube (estratégia de cota, descoberta e snapshot) |
| [`docs/05-motor-monetizacao-e-score.md`](docs/05-motor-monetizacao-e-score.md) | Detecção de monetização e score de "nicho viral" |
| [`docs/06-dashboard.md`](docs/06-dashboard.md) | Especificação do dashboard web |
| [`docs/07-infraestrutura-e-operacao.md`](docs/07-infraestrutura-e-operacao.md) | Deploy, agendamento, custos, segurança, backup e restore |
| [`docs/08-roadmap-de-fases.md`](docs/08-roadmap-de-fases.md) | Divisão em fases com prompts prontos para o Claude Code |
| [`docs/09-requisitos-nao-funcionais.md`](docs/09-requisitos-nao-funcionais.md) | Checklist consolidado de performance, segurança, custo e escalabilidade |
| [`docs/10-validacao-e-ajustes.md`](docs/10-validacao-e-ajustes.md) | Etapa 5: validação pós-entrega contra critérios de aceite e processo de ajuste |

## Como rodar

```
cp .env.example .env      # preencha YOUTUBE_API_KEY, credenciais do Postgres e DASHBOARD_PASSWORD
docker compose up -d --build
alembic upgrade head      # cria o schema
python -m src.db.seed     # 3 nichos de exemplo
```

Dashboard em `http://localhost:8501` (senha = `DASHBOARD_PASSWORD`), API em `http://localhost:8010`.

Os jobs rodam sozinhos nos horários de `DISCOVERY_CRON` e `SNAPSHOT_CRON`. Para disparar manualmente:

```
python -m src.scheduler.jobs discovery    # descobre canais novos
python -m src.scheduler.jobs snapshot     # atualiza métricas, calcula score e dispara alertas
python -m src.scheduler.jobs enrichment   # recalcula scores sem coletar (útil após mudar pesos)
```

## Resumo para quem vai apresentar isso ao chefe

O YouTube tem uma API oficial gratuita e estável (YouTube Data API v3) que sustenta o produto inteiro: descoberta de canais novos, histórico de crescimento, detecção de sinais de monetização e um score para priorizar o que vale olhar primeiro. O sistema está construído e rodando — os números abaixo são de coletas reais, não de exemplo.

### O que o sistema já achou

| Indicador | Número real |
|---|---|
| Canais monitorados | 67, em 3 nichos (finanças pessoais 29, pets exóticos 21, produtividade 12) |
| Tamanho dos canais descobertos | mediana de **1.580 inscritos** (de 1 a 99.900) |
| Canais com algum sinal de monetização | 44 de 67 (**66%**) |
| Sinais detectados | 83 no total: 43 de elegibilidade ao YouTube Partner Program, 23 de infoproduto, 14 de link de afiliado, 3 de comunidade paga |

A mediana de 1.580 inscritos é o dado que mostra que o filtro está fazendo o trabalho certo: o sistema está trazendo canais pequenos com vídeos recentes acima do seu tamanho — que é onde mora a oportunidade — e não recadastrando canais que já estouraram.

Cada sinal de monetização vem com a **evidência** que o gerou (a URL ou o trecho de texto), para conferência manual antes de qualquer decisão. Exemplo real encontrado: um canal de finanças com 181 inscritos e um link de pagamento Kiwify na descrição dos vídeos — canal pequeno que já está vendendo.

### Custo operacional

Consumo real até agora: **1.432 unidades de cota em 6 execuções**, contra um limite gratuito de 10.000 por dia. Uma rodada completa custou 713 unidades para descobrir 43 canais novos e 201 para atualizar as métricas de 67 canais (3 unidades por canal). Nesse ritmo, a cota gratuita comporta **milhares de canais monitorados** sem custo — o gasto real do MVP é só a hospedagem.

### O que ainda não dá para afirmar

O componente de **crescimento** do score ainda vale pouco: ele compara o canal com ele mesmo 7 dias atrás, e a maior parte da base foi descoberta há poucos dias. Depois de uma semana de coleta diária esse número passa a valer, e o ranking muda. Hoje quem sustenta a priorização é a detecção de monetização, que já funciona plenamente.

O sistema **estima** monetização por evidência indireta — nunca sabe a receita real de um canal de terceiros, e nenhuma ferramenta de mercado sabe (ver `docs/01-visao-geral-e-escopo.md`).
