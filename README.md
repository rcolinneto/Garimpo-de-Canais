# Garimpo de Canais (YouTube) — Documentação de Projeto

Sistema para descobrir automaticamente canais do YouTube em crescimento acelerado que estão monetizando nichos virais, com um dashboard web para acompanhamento.

Este pacote é a especificação completa do projeto, dividida em partes, pensada para ser usada como insumo direto para o **Claude Code** construir o software fase por fase.

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
| [`docs/01-visao-geral-e-escopo.md`](docs/01-visao-geral-e-escopo.md) | Objetivo, escopo e critérios de sucesso |
| [`docs/02-arquitetura.md`](docs/02-arquitetura.md) | Arquitetura geral, componentes, stack técnica, diagrama |
| [`docs/03-modelo-de-dados.md`](docs/03-modelo-de-dados.md) | Schema do banco de dados |
| [`docs/04-coleta-youtube.md`](docs/04-coleta-youtube.md) | Módulo de coleta do YouTube (estratégia de cota, descoberta e snapshot) |
| [`docs/05-motor-monetizacao-e-score.md`](docs/05-motor-monetizacao-e-score.md) | Detecção de monetização e score de "nicho viral" |
| [`docs/06-dashboard.md`](docs/06-dashboard.md) | Especificação do dashboard web |
| [`docs/07-infraestrutura-e-operacao.md`](docs/07-infraestrutura-e-operacao.md) | Deploy, agendamento, custos, segurança |
| [`docs/08-roadmap-de-fases.md`](docs/08-roadmap-de-fases.md) | Divisão em fases com prompts prontos para o Claude Code |

## Resumo para quem vai apresentar isso ao chefe

O YouTube tem uma API oficial gratuita e estável (YouTube Data API v3) que sustenta o produto inteiro: descoberta de canais novos, histórico de crescimento, detecção de sinais de monetização e um score para priorizar o que vale olhar primeiro. Custo operacional do MVP é próximo de zero — a única cota a respeitar é a gratuita da própria API (10.000 unidades/dia), e todo o desenho de coleta em `docs/04-coleta-youtube.md` já é feito para caber dentro dela.
