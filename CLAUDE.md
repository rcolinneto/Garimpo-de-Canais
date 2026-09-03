# Garimpo de Canais — Instruções para o Claude Code

Este projeto constrói um sistema que descobre automaticamente canais do YouTube em crescimento que estão monetizando nichos virais, com um dashboard web de acompanhamento.

## Antes de qualquer tarefa

Toda a especificação do projeto está em `docs/`. Antes de implementar qualquer parte, leia:
1. `docs/01-visao-geral-e-escopo.md` — objetivo e escopo.
2. `docs/02-arquitetura.md` — arquitetura, stack e estrutura de pastas obrigatória.
3. O documento específico da fase que está sendo trabalhada (`docs/08-roadmap-de-fases.md` indica qual ler para cada fase).

Trabalhe **uma fase do roadmap por vez** (`docs/08-roadmap-de-fases.md`).

## Convenções do projeto

- Python 3.12+, gerenciado via `pyproject.toml`.
- Estrutura de pastas: seguir exatamente o layout descrito em `docs/02-arquitetura.md` (`src/collectors`, `src/enrichment`, `src/db`, `src/scheduler`, `src/api`, `src/dashboard`, `src/config`).
- Banco: PostgreSQL via SQLAlchemy + Alembic. Toda mudança de schema é uma migration nova, nunca editar uma migration já aplicada.
- Toda a coleta de dados usa a YouTube Data API v3 — respeitar a estratégia de economia de cota descrita em `docs/04-coleta-youtube.md` (search.list é caro, channels.list/videos.list/playlistItems.list são baratos).
- Segredos (chaves de API, credenciais de banco/SMTP) sempre via variáveis de ambiente (`.env`, nunca commitado); manter `.env.example` atualizado a cada nova variável introduzida.
- Testes com `pytest` para lógica de coleta, motor de score e endpoints da API. Rodar a suíte antes de considerar uma fase concluída.

## Ao terminar uma fase

- Rodar `docker-compose up` e validar manualmente que o que foi construído funciona de ponta a ponta.
- Atualizar `.env.example` se novas variáveis foram introduzidas.
- Resumir no fim da sessão o que foi implementado e qual é a próxima fase, conforme `docs/08-roadmap-de-fases.md`.
