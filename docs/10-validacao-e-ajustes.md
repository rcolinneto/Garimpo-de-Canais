# 10 — Validação Pós-Entrega e Processo de Ajuste (Etapa 5)

Este documento define como validar o que foi construído contra os critérios de aceite, e como tratar pedidos de ajuste depois da entrega — tanto ao final de cada fase do roadmap quanto na entrega final do MVP ao chefe. Nenhum dos outros documentos cobria essa etapa; sem ela, "pronto" fica no critério subjetivo de quem construiu.

## Checklist de validação por fase

Ao final de cada fase do roadmap (`08-roadmap-de-fases.md`), antes de marcar como concluída, confirme:

1. **Funciona de ponta a ponta**: `docker-compose up` sobe sem erro, o endpoint/tela relevante da fase responde com dados reais (não só com mock).
2. **Bate com a especificação**: reler o documento de referência da fase (ex.: Fase 2 → `04-coleta-youtube.md`) e conferir item a item, não confiar de memória.
3. **Requisitos não-funcionais relevantes à fase** (`09-requisitos-nao-funcionais.md`) foram respeitados — ex.: na Fase 2, checar `api_units_consumed` real contra o limite esperado.
4. **Testes automatizados** (quando a fase os previu) passam.
5. **Commit e push feitos**, com mensagem clara referenciando a fase.

## Validação da entrega final ao chefe (fim da Fase 6)

Antes de apresentar o sistema como pronto para uso real:

1. Rodar o sistema por pelo menos um ciclo completo (descoberta + snapshot + score + alerta) com dados reais, não só dados de teste/seed.
2. Revisar manualmente uma amostra de 10-15 canais descobertos: fazem sentido para os nichos configurados? Os sinais de monetização detectados são plausíveis quando conferidos manualmente (abrindo o canal de verdade)?
3. Conferir cada item dos "Critérios de sucesso" definidos em `01-visao-geral-e-escopo.md` — não avançar para "concluído" com algum item ainda pendente sem que isso seja uma decisão explícita e comunicada.
4. Apresentar o dashboard ao chefe **antes** de considerar o projeto encerrado, e coletar feedback direto sobre: os canais/nichos mostrados são úteis na prática? A UI é fácil de usar sem ajuda técnica? Falta alguma informação para decisão?
5. Só depois dessa validação com o chefe o projeto passa de "MVP em construção" para "em operação".

## Processo de ajuste (pós-entrega)

Pedidos de ajuste depois que o sistema já está em operação seguem este fluxo, para não virarem mudanças silenciosas de escopo:

1. **Registrar o pedido**: o que o chefe pediu, e por quê (qual dor ou necessidade motivou).
2. **Classificar**:
   - *Correção*: o sistema não está fazendo o que a documentação já prevê (bug) — corrige direto, sem necessidade de nova rodada de alinhamento.
   - *Ajuste de calibração*: os pesos do score, os RPMs por nicho, os limiares de alerta não estão gerando resultados úteis — ajustar valores em `config/settings.py`/`config/niches.yaml` (esses parâmetros já foram desenhados para serem configuráveis exatamente por isso, ver `05-motor-monetizacao-e-score.md`).
   - *Mudança de escopo*: pedido que não estava no PRD original (ex.: "quero TikTok também", "quero um relatório em PDF automático") — volta para uma mini rodada de alinhamento (mesmo modelo de `00-brainstorm-e-alinhamento.md`), com impacto em custo/prazo avaliado antes de qualquer implementação.
3. **Atualizar a documentação correspondente** antes de implementar — nunca alterar código de forma que a documentação passe a mentir sobre o comportamento real do sistema. Se `01-visao-geral-e-escopo.md` muda, registrar a mudança (o pivô de multi-plataforma para YouTube-only feito durante a especificação deste projeto é um exemplo real desse processo funcionando).
4. **Rodar novamente o checklist de validação** relevante (fase específica ou entrega final, conforme o tamanho do ajuste) antes de considerar o ajuste concluído.

## Cadência sugerida

Mesmo sem pedido explícito do chefe, revisitar mensalmente: os nichos configurados ainda são os de interesse? As regras de monetização (`05-motor-monetizacao-e-score.md`) continuam pegando os padrões de link/produto que existem hoje no mercado, ou surgiram novos formatos que valem adicionar? Isso evita que o sistema "envelheça" silenciosamente enquanto continua rodando sem erro.
