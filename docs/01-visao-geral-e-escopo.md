# 01 — Visão Geral e Escopo

## Objetivo do produto

Automatizar a "garimpagem" de canais do YouTube que estejam (a) crescendo rapidamente e (b) mostrando sinais de monetização dentro de nichos que estão viralizando — para servir como radar de oportunidades de conteúdo e negócio (identificar nichos quentes antes de saturarem, encontrar formatos e modelos de monetização que já estão funcionando para outros criadores).

O sistema deve, de forma recorrente e sem intervenção manual:

1. Buscar canais novos ou pouco conhecidos que estejam em trajetória de crescimento acima da média.
2. Acompanhar a evolução de métricas desses canais ao longo do tempo (inscritos, views, engajamento).
3. Detectar sinais de que o canal já está monetizando (produtos próprios, afiliados, infoprodutos, patrocínio, etc.).
4. Calcular um "score de nicho viral" que ajude a priorizar o que vale a pena olhar primeiro.
5. Apresentar tudo isso em um dashboard web para consumo do seu chefe.

## Escopo

- Plataforma: **YouTube**, via YouTube Data API v3 (API oficial, gratuita).
- Nichos configuráveis por lista de palavras-chave/categorias (o chefe define os nichos de interesse; o sistema não "adivinha" nichos do zero).
- Coleta recorrente (diária) com histórico de métricas por canal.
- Motor de score e detecção de monetização baseado em heurísticas (ver `05-motor-monetizacao-e-score.md`).
- Dashboard web para explorar os resultados.

## Fora de escopo

- Outras redes sociais (TikTok, Instagram, etc.) — fica de fora deliberadamente: o YouTube tem API oficial de descoberta gratuita e estável; outras plataformas exigiriam provedores de dados pagos de terceiros, o que é uma decisão de orçamento separada e não faz parte deste projeto.
- Detecção de monetização real (receita de fato) — o sistema **estima**, nunca sabe o valor real que um canal de terceiros fatura. Nenhuma ferramenta de mercado tem acesso a isso.
- Geração automática de ideias de conteúdo/roteiros a partir dos achados (pode ser uma fase futura separada, fora deste escopo).

## Critérios de sucesso

- O chefe consegue, sem ajuda técnica, abrir o dashboard e ver quais canais novos surgiram nos últimos X dias, ordenados por score, com indicação de que sinais de monetização foram encontrados.
- O histórico de crescimento de um canal é visível em gráfico (não só o número do dia).
- O sistema roda sozinho (job agendado) sem precisar disparar manualmente.
- Custo operacional é próximo de zero (dentro da cota gratuita da API + hospedagem simples).
