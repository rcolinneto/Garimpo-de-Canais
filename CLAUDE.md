# Garimpo de Canais — Instruções para o Claude Code

## Contexto de negócio

- **Dono do produto**: o chefe de Renato (patrocinador do pedido), na agência de marketing onde Renato trabalha como analista. É quem consome o resultado final via dashboard e para quem os critérios de sucesso devem fazer sentido.
- **Executor/mantenedor**: Renato, com apoio do Claude Code para implementação.
- **Objetivo**: um radar automático de canais do YouTube em crescimento que estão monetizando nichos virais — insumo para identificar oportunidades de conteúdo e formatos/modelos de monetização que já estão funcionando para outros criadores.
- **Como se relaciona com a operação da agência**: este sistema é **insumo para estratégia de conteúdo** (o que produzir, em qual nicho, com qual abordagem de monetização) — **não é uma ferramenta de gestão de campanha** (não substitui, nem se integra com, ferramentas de mídia paga, relatórios de cliente ou operação de tráfego pago da agência). Não expandir o escopo para essas funções sem uma nova rodada de alinhamento explícita (ver `docs/00-brainstorm-e-alinhamento.md`).

## Antes de qualquer tarefa

Toda a especificação do projeto está em `docs/`. Antes de implementar qualquer parte, leia, na ordem:
1. `docs/00-brainstorm-e-alinhamento.md` — como o escopo chegou a ser o que é hoje (inclui decisões descartadas, para não serem re-propostas sem necessidade).
2. `docs/01-visao-geral-e-escopo.md` — objetivo, escopo e critérios de sucesso.
3. `docs/02-arquitetura.md` — arquitetura, stack e estrutura de pastas obrigatória.
4. `docs/09-requisitos-nao-funcionais.md` — checklist de requisitos não-funcionais (performance, segurança, custo) que qualquer implementação deve respeitar.
5. O documento específico da fase que está sendo trabalhada (`docs/08-roadmap-de-fases.md` indica qual ler para cada fase).

Trabalhe **uma fase do roadmap por vez** (`docs/08-roadmap-de-fases.md`). Ao final de cada fase, rodar o checklist de `docs/10-validacao-e-ajustes.md` antes de marcar como concluída.

## Convenções do projeto

- Python 3.12+, gerenciado via `pyproject.toml`.
- Estrutura de pastas: seguir exatamente o layout descrito em `docs/02-arquitetura.md` (`src/collectors`, `src/enrichment`, `src/db`, `src/scheduler`, `src/api`, `src/dashboard`, `src/config`).
- Banco: PostgreSQL via SQLAlchemy + Alembic. Toda mudança de schema é uma migration nova, nunca editar uma migration já aplicada.
- Toda a coleta de dados usa a YouTube Data API v3 — respeitar a estratégia de economia de cota descrita em `docs/04-coleta-youtube.md` (search.list é caro, channels.list/videos.list/playlistItems.list são baratos).
- Segredos (chaves de API, credenciais de banco/SMTP) sempre via variáveis de ambiente (`.env`, nunca commitado); manter `.env.example` atualizado a cada nova variável introduzida.
- Testes com `pytest` para lógica de coleta, motor de score e endpoints da API. Rodar a suíte antes de considerar uma fase concluída.

## Ao terminar uma fase

- Rodar `docker-compose up` e validar manualmente que o que foi construído funciona de ponta a ponta.
- Rodar o checklist de validação por fase em `docs/10-validacao-e-ajustes.md`.
- Atualizar `.env.example` se novas variáveis foram introduzidas.
- Se a fase revelar necessidade de mudar escopo (não só implementação), registrar isso como uma nova rodada de alinhamento antes de implementar — não mudar o PRD silenciosamente (ver processo de ajuste em `docs/10-validacao-e-ajustes.md`).
- Resumir no fim da sessão o que foi implementado e qual é a próxima fase, conforme `docs/08-roadmap-de-fases.md`.
