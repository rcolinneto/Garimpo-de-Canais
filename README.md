# Garimpo de Canais (YouTube)

Sistema que descobre automaticamente canais do YouTube em crescimento que estão monetizando nichos virais — e, sobre isso, identifica **brechas virais**: formatos que já provaram demanda e cujo espaço ainda não foi ocupado em outro mercado.

Este repositório contém a especificação completa (em `docs/`) e a implementação, construída fase a fase com o **Claude Code**. As **9 fases do roadmap estão concluídas**:

- **Fases 1–6** — o radar: coleta, motor de score, API, dashboard e alertas.
- **Fases 7–9** — a camada de oportunidade (metodologia Brecha Viral): detecção de vídeos fora da curva, anatomia do título e mapeamento de brechas por mercado.

## Como usar esta documentação com o Claude Code

1. Deixe o `CLAUDE.md` na raiz — o Claude Code lê esse arquivo ao iniciar a sessão, e ele aponta para todos os documentos de `docs/`.
2. Siga o roadmap em `docs/08-roadmap-de-fases.md`. Cada fase tem um prompt pronto; trabalhe **uma por vez**, revisando antes de avançar.
3. Mudança de escopo **não** entra por edição silenciosa do PRD: abre-se uma rodada de alinhamento (o processo está em `docs/10`, e `docs/00b` é um exemplo real dele sendo usado).

## Índice dos documentos

| Arquivo | Conteúdo |
|---|---|
| [`docs/00-brainstorm-e-alinhamento.md`](docs/00-brainstorm-e-alinhamento.md) | Pedido original, perguntas de alinhamento, opções descartadas e por quê |
| [`docs/00b-alinhamento-brecha-viral.md`](docs/00b-alinhamento-brecha-viral.md) | 2ª rodada de alinhamento: a metodologia Brecha Viral, decisões e limites |
| [`docs/01-visao-geral-e-escopo.md`](docs/01-visao-geral-e-escopo.md) | Objetivo, escopo e critérios de sucesso |
| [`docs/02-arquitetura.md`](docs/02-arquitetura.md) | Arquitetura, componentes, stack, diagrama |
| [`docs/03-modelo-de-dados.md`](docs/03-modelo-de-dados.md) | Schema do banco |
| [`docs/04-coleta-youtube.md`](docs/04-coleta-youtube.md) | Coleta do YouTube: estratégia de cota, descoberta, snapshot e mercados |
| [`docs/05-motor-monetizacao-e-score.md`](docs/05-motor-monetizacao-e-score.md) | Monetização, score de nicho, outlier, anatomia do título e score de oportunidade |
| [`docs/06-dashboard.md`](docs/06-dashboard.md) | Especificação das 6 telas |
| [`docs/07-infraestrutura-e-operacao.md`](docs/07-infraestrutura-e-operacao.md) | Deploy, migrations, agendamento, custos, segurança, backup |
| [`docs/08-roadmap-de-fases.md`](docs/08-roadmap-de-fases.md) | As 9 fases, com prompts prontos |
| [`docs/09-requisitos-nao-funcionais.md`](docs/09-requisitos-nao-funcionais.md) | Checklist de performance, segurança, custo e escalabilidade |
| [`docs/10-validacao-e-ajustes.md`](docs/10-validacao-e-ajustes.md) | Validação pós-entrega e processo de ajuste |
| [`docs/brecha-viral/metodologia.md`](docs/brecha-viral/metodologia.md) | A metodologia como fonte de referência (resumo do treinamento) |

## Como rodar

```
cp .env.example .env      # preencha YOUTUBE_API_KEY, credenciais do Postgres e DASHBOARD_PASSWORD
docker compose up -d --build
python -m src.db.seed     # 3 nichos de exemplo (opcional)
```

O schema é criado sozinho: a API roda `alembic upgrade head` ao subir. Esse passo era manual e foi esquecido em três fases seguidas, quebrando a produção de forma parcial e silenciosa — ver `docs/07`.

Dashboard em `http://localhost:8501` (senha = `DASHBOARD_PASSWORD`), API em `http://localhost:8010`.

Os jobs rodam sozinhos nos horários de `DISCOVERY_CRON` e `SNAPSHOT_CRON`. Para disparar manualmente:

```
python -m src.scheduler.jobs discovery    # descobre canais novos
python -m src.scheduler.jobs snapshot     # métricas, score, vídeos, outliers, brechas e alertas
python -m src.scheduler.jobs enrichment   # recalcula scores sem coletar (após mudar pesos)
```

### Qualidade

```
python -m pytest              # 194 testes
python -m ruff check src tests streamlit_app.py
```

Os testes de integração são **pulados** se o Postgres não estiver de pé — não falham. Para rodá-los fora do Docker, aponte o banco para a porta publicada no host:

```
DATABASE_URL=postgresql://garimpo:...@localhost:5433/garimpo python -m pytest
```

## Estado real do sistema

Números de coletas reais, medidos em 2026-09-24 — não são exemplo.

| Indicador | Número |
|---|---|
| Canais monitorados | **134**, em 3 nichos (Curiosidades 29, Jazz 27, Futebol 21) + 57 sem nicho |
| Tamanho dos canais | mediana de **13.800 inscritos** (de 10 a 101.000) |
| Canais com algum sinal de monetização | 109 de 134 |
| Brechas mapeadas | 3, no mercado US/en |
| Consumo de cota | **650 a 1.300 unidades/dia**, de um limite gratuito de 10.000 |

### O que estes números não dizem

**"109 de 134 com sinal de monetização" é menos impressionante do que parece.** Dos 116 sinais detectados, **105 são apenas elegibilidade ao YouTube Partner Program** — que significa "o canal tem inscritos suficientes para monetizar", não que ele monetiza. Os sinais fortes (infoproduto, link de afiliado, loja própria) somam 11.

Isso mudou junto com os nichos: quando a base era finanças e produtividade, os sinais fortes eram 40 de 83. Jazz, futebol e curiosidades são entretenimento — vendem menos infoproduto por natureza. Não é defeito do detector; é o retrato de nichos diferentes. Vale considerar ao escolher nichos, porque o score de monetização perde poder de discriminação em nichos de entretenimento.

**57 canais não têm nicho.** Vêm da coleta barata de "vídeos em alta" (1 unidade de cota), que acha canais fora dos nichos configurados. Dá para isolá-los no filtro da Tela 2.

**O score de crescimento tem um buraco de 3 dias.** Entre 21 e 23/09 o snapshot falhou (ver `docs/07`), e o YouTube não devolve métricas retroativas. Corrige-se sozinho conforme novos snapshots acumulam.

### Os limites que o sistema declara

- **Estima** monetização por evidência indireta — nunca sabe a receita real de um canal de terceiros, e nenhuma ferramenta de mercado sabe.
- **Não decide** que uma brecha é boa: ordena candidatas por evidência e mostra o porquê de cada nota.
- **Não responde** se um assunto faz sentido culturalmente em outro país — a pergunta aparece na tela como pendência humana, e fica fora da fórmula.

## Hospedagem

O caminho gratuito sem cartão de crédito está documentado em `docs/07`: API no Render, banco no Neon, dashboard no Streamlit Cloud e coleta agendada via GitHub Actions. Os arquivos `streamlit_app.py` e `requirements.txt` na raiz existem só para o Streamlit Cloud — o motivo de cada um está no cabeçalho deles.
