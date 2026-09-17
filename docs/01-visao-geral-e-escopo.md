# 01 — Visão Geral e Escopo

> **Revisado em 2026-09-17** pela rodada de alinhamento `00b-alinhamento-brecha-viral.md`, que somou ao produto a metodologia Brecha Viral. O radar de canais descrito abaixo continua valendo integralmente — ele virou a **base** sobre a qual a camada de oportunidade funciona.

## Objetivo do produto

Automatizar a "garimpagem" de canais do YouTube que estejam (a) crescendo rapidamente e (b) mostrando sinais de monetização dentro de nichos que estão viralizando — para servir como radar de oportunidades de conteúdo e negócio (identificar nichos quentes antes de saturarem, encontrar formatos e modelos de monetização que já estão funcionando para outros criadores).

A partir dessa base, o sistema também identifica **brechas virais**: formatos que já provaram demanda e cujo ângulo ou mercado ainda não foi ocupado por ninguém. A diferença entre as duas perguntas é o que separa as duas camadas:

- **Camada radar** (original): *quais canais estão crescendo e monetizando nos nichos que eu configurei?*
- **Camada oportunidade** (nova): *qual formato já validado eu posso ocupar, com qual ângulo e em qual mercado, sem disputar espaço com ninguém?*

O sistema deve, de forma recorrente e sem intervenção manual:

1. Buscar canais novos ou pouco conhecidos que estejam em trajetória de crescimento acima da média.
2. Acompanhar a evolução de métricas desses canais ao longo do tempo (inscritos, views, engajamento).
3. Detectar sinais de que o canal já está monetizando (produtos próprios, afiliados, infoprodutos, patrocínio, etc.).
4. Calcular um "score de nicho viral" que ajude a priorizar o que vale a pena olhar primeiro.
5. **Identificar vídeos "outlier"** — os que performam muito acima da média do próprio canal, sinal de que algo específico naquele vídeo funcionou.
6. **Dissecar o formato desses vídeos** em peças reconhecíveis (número alto, autoridade emprestada, gatilho de medo/desejo/curiosidade) e registrar a evidência de cada uma.
7. **Avaliar mercados/idiomas** onde o mesmo formato ainda não tem canal atendendo, com a estimativa de RPM daquele país.
8. Apresentar tudo isso em um dashboard web para consumo do seu chefe.

## Escopo

- Plataforma: **YouTube**, via YouTube Data API v3 (API oficial, gratuita).
- Nichos configuráveis por lista de palavras-chave/categorias (o chefe define os nichos de interesse; o sistema não "adivinha" nichos do zero).
- Coleta recorrente (diária) com histórico de métricas por canal **e por vídeo**.
- Motor de score e detecção de monetização baseado em heurísticas (ver `05-motor-monetizacao-e-score.md`).
- **Detecção de outliers e anatomia de título**, pelo mesmo princípio de heurística explicável com evidência anexada.
- **Dimensão de mercado/idioma** usando `regionCode` e `relevanceLanguage` — parâmetros nativos da API, sem proxy nem spoofing de localização (ver justificativa em `00b`).
- Dashboard web para explorar os resultados.

## Fora de escopo

- Outras redes sociais (TikTok, Instagram, etc.) — fica de fora deliberadamente: o YouTube tem API oficial de descoberta gratuita e estável; outras plataformas exigiriam provedores de dados pagos de terceiros, o que é uma decisão de orçamento separada e não faz parte deste projeto.
- Detecção de monetização real (receita de fato) — o sistema **estima**, nunca sabe o valor real que um canal de terceiros fatura. Nenhuma ferramenta de mercado tem acesso a isso.
- Geração automática de ideias de conteúdo/roteiros a partir dos achados (pode ser uma fase futura separada, fora deste escopo).
- **Decidir sozinho que uma brecha é boa.** O sistema ordena candidatas por evidência e mostra o porquê; julgar se um ângulo faz sentido cultural naquele país (a 4ª das "4 perguntas") continua sendo leitura humana.
- **Proxy ou spoofing de localização** para navegar o YouTube como outro país. A API oficial aceita `regionCode`/`relevanceLanguage`, então a prática ensinada no curso é desnecessária aqui — e estaria fora dos Termos de Uso.
- **Produzir o conteúdo** (etapa "OCUPAR" da metodologia). O sistema entrega a oportunidade validada; a produção é do time.

## Critérios de sucesso

- O chefe consegue, sem ajuda técnica, abrir o dashboard e ver quais canais novos surgiram nos últimos X dias, ordenados por score, com indicação de que sinais de monetização foram encontrados.
- O histórico de crescimento de um canal é visível em gráfico (não só o número do dia).
- O sistema roda sozinho (job agendado) sem precisar disparar manualmente.
- Custo operacional é próximo de zero (dentro da cota gratuita da API + hospedagem simples).
- **O chefe vê uma lista de brechas candidatas** com, em cada uma: o vídeo que provou a demanda, as peças do formato que foram reconhecidas, o mercado sugerido e o que ainda falta validar manualmente.
- **Nenhuma brecha aparece sem a prova que a sustenta** — mesma regra que já vale para sinais de monetização.
