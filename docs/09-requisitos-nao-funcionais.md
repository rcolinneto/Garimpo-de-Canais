# 09 — Requisitos Não-Funcionais

Este documento consolida, em um único lugar, requisitos que hoje aparecem espalhados pela arquitetura (`02-arquitetura.md`), pela coleta (`04-coleta-youtube.md`) e pela infraestrutura (`07-infraestrutura-e-operacao.md`). Nada aqui é novo tecnicamente — é a formalização do que já estava implícito, para servir como checklist de aceite e não depender de garimpar cada documento individualmente.

## Performance e limites

- **Cota da API do YouTube**: 10.000 unidades/dia por chave (reset à meia-noite Pacífico). `search.list` = 100 unidades; `channels.list`/`videos.list`/`playlistItems.list` = 1 unidade. O job de descoberta deve consumir no máximo uma fração definida da cota diária (sugestão: até 30%, deixando o restante para snapshots); o job de snapshot deve escalar para milhares de canais dentro da cota restante usando só endpoints de 1 unidade. Detalhe completo em `04-coleta-youtube.md`.
- **Tempo de execução dos jobs**: o job de snapshot diário deve terminar dentro da janela noturna configurada (ex.: completar em até 2 horas para a base de canais esperada no primeiro ano) para não atrasar a atualização do dashboard pela manhã.
- **Tempo de resposta do dashboard**: consultas da Tela 2 (listagem com filtros) devem responder em menos de 2 segundos para o volume esperado (até alguns milhares de canais) — se isso deixar de ser verdade, é sinal de que faltam índices ou de que é hora de paginar a listagem.

## Escalabilidade

- Volume-alvo do MVP: dezenas de nichos, até alguns milhares de canais monitorados. A arquitetura com APScheduler + processo único é suficiente até essa ordem de grandeza.
- Gatilho de migração para Celery + Redis (ver `02-arquitetura.md`): quando o tempo de execução dos jobs passar a estourar a janela disponível, ou quando o número de chaves de API precisar ser rotacionado com frequência para dar conta do volume.
- Gatilho de migração do dashboard de Streamlit para FastAPI + React: necessidade de múltiplos usuários com login individual/papéis distintos.

## Segurança

- Nenhum segredo (chave da API do YouTube, credenciais de banco, credenciais SMTP) em código-fonte ou versionado no git — sempre via `.env`, com `.env.example` documentando as chaves sem valores reais.
- Chave da API do YouTube restrita, no Google Cloud Console, apenas à YouTube Data API v3 (ver histórico de configuração — já aplicado neste projeto).
- Dashboard protegido por senha (mínimo aceitável para uso interno de pequeno time); reavaliar para autenticação individual se o número de usuários crescer.
- Acesso ao banco de produção restrito à rede interna da aplicação (não exposto publicamente na internet).

## Disponibilidade e confiabilidade

- Toda execução de job (descoberta e snapshot) é registrada em `collection_runs`, incluindo falhas parciais — essa tabela é a fonte de verdade para saber se a coleta está saudável.
- Falha de job dispara alerta por e-mail (mesmo mecanismo da Fase 6) para não deixar a equipe descobrir dados desatualizados só ao abrir o dashboard dias depois.
- Meta de disponibilidade do dashboard: uso interno, não crítico — não há exigência de alta disponibilidade (multi-região, failover automático); reinício manual do container em caso de queda é aceitável no MVP.

## Custo

- Meta: custo operacional do MVP (YouTube apenas) próximo de zero, limitado ao valor de uma VPS pequena (ver `07-infraestrutura-e-operacao.md`). Qualquer extensão que introduza custo recorrente relevante (ex.: provedor de dados de outra plataforma, upgrade de infraestrutura) exige aprovação explícita do chefe antes de ser implementada — não é uma decisão técnica unilateral.

## Manutenibilidade e explicabilidade

- Regras de detecção de monetização e cálculo de score são heurísticas explícitas (regex, listas, fórmulas com pesos configuráveis), não um modelo caixa-preta — qualquer resultado do dashboard deve poder ser explicado ao chefe em termos simples ("pontuou alto porque cresceu X% e tem sinal de loja própria").
- Toda mudança de schema do banco é uma migration Alembic versionada — nunca alteração manual direta no banco de produção.

## Observabilidade

- Logs estruturados (INFO/ERROR) para toda execução de job.
- `collection_runs.api_units_consumed` deve ser monitorado ao longo do tempo para antecipar a necessidade de rotacionar/adicionar chaves de API antes de a cota virar um bloqueio real.

## Rastreamento deste documento

Cada requisito acima referencia o documento onde a decisão técnica correspondente está detalhada — este arquivo não substitui aqueles, apenas os indexa como checklist único de aceite não-funcional, a ser conferido antes de considerar qualquer fase "pronta para produção" (ver também `10-validacao-e-ajustes.md`).
