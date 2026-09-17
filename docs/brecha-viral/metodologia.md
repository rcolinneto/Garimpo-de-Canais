# Metodologia Brecha Viral — referência

Resumo estruturado das Aulas 1–3 do mini treinamento "Brecha Viral" (comprado
por Breno em 2026-09-16, plataforma Cakto). Curso ainda em gravação — módulos
seguintes liberados progressivamente. Transcrições brutas em `raw/`.

Este documento é **a fonte da metodologia**, não a especificação do sistema. O
que o software faz com ela está em `../00b-alinhamento-brecha-viral.md` e nos
documentos numerados que ele altera.

## Conceito central

> "Quem copia o assunto disputa uma audiência que já tem dono. Quem copia o
> formato e troca o assunto herda a audiência inteira sem disputar com ninguém."

**Brecha viral** = uma oportunidade dentro de um assunto que já está
performando (vídeo/canal validado no YouTube), onde existe um **ângulo** ou um
**mercado (país/idioma)** que os concorrentes ainda não ocuparam.

O erro mais comum — e que mata a maioria dos canais — é copiar e colar um vídeo
ou título que já viralizou. Quem chegou primeiro num assunto já "ensinou pro
algoritmo" que é a melhor opção; copiar só dilui a audiência entre os que
chegaram depois.

## As 3 condições (precisam valer ao mesmo tempo)

Sem as três, não é brecha:

1. **O assunto já performa** — existe um vídeo comprovando demanda. Não é
   aposta, é leitura de dado real: volume e viralização comprovados.
2. **Existe um ângulo vago** — o vídeo/canal original não cobre tudo: sobrou um
   recorte, um público ou uma pergunta sem resposta.
3. **Os concorrentes não ocuparam o espaço** — quem copia o vídeo validado
   normalmente só faz Ctrl+C/Ctrl+V, sem mudar ângulo ou formato, deixando a
   brecha aberta.

## As 2 dimensões da brecha

| Dimensão | O que é | Risco |
|---|---|---|
| **Ângulo novo** | Mesmo idioma/mercado do canal original, atacando um recorte ou pergunta que ele deixou vago | Ainda divide espaço com o canal original |
| **Mercado/país novo** | Mesmo ângulo validado, levado para outro idioma/país onde ainda não há canal atendendo | Alguém pode já ter pensado nisso — validar antes |
| **Brecha dupla** | Ângulo novo **+** país novo ao mesmo tempo | Chance de acerto muito maior: não compete com ninguém e "cria a tendência" usando prova que já existe |

Por que levar para outro país funciona: a demanda já foi provada; comportamento
humano (medo, curiosidade, dinheiro) não muda entre idiomas; e a concorrência
não atravessa fronteira porque quem replica normalmente copia sem entender o
porquê do sucesso.

## As 4 perguntas antes de entrar num mercado

1. **Tem volume?** Existe gente procurando esse assunto nesse idioma.
2. **Tem canal atendendo esse assunto?** Se só aparecem vídeos antigos ou de
   canais pequenos = brecha confirmada, mesmo havendo canais grandes no tema
   geral.
3. **O RPM compensa?** Países ricos pagam mais por mil views. Inglês = maior
   CPM, mais concorrência; alemão/italiano/polonês = CPM bom com menos
   concorrência, porém menos falantes, logo menos alcance. É conta.
4. **O assunto faz sentido nesse país?** Clima, hábitos, costumes e cultura
   mudam a relevância de um tema — não traduz 1:1.

Quatro respostas boas → brecha de mercado confirmada. Trocando também o ângulo
→ brecha dupla.

## Anatomia de um título viral

Exemplo do treinamento: *"25 esconderijos que ladrões nunca verificam (policiais
aposentados usam todos eles)"* — 166 mil views em 9 dias.

- **Número alto** — quantifica a promessa (25, 23, 17…)
- **Objeto concreto** — "esconderijo", não algo abstrato
- **Autoridade emprestada** — "policiais aposentados" dá credibilidade sem o
  criador precisar provar nada
- **Medo/desejo útil** — segurança da casa; adaptável para o mesmo gatilho com
  público diferente (mulher sozinha em casa, apartamento, etc.)

## Vídeo "Outlier"

Um vídeo que performa muito acima da média do próprio canal — ex.: canal com
vídeos de 400–800 mil em 3–4 meses e um vídeo novo que bateu 270 mil em 3 dias.
A distância entre o ritmo normal do canal e esse pico é o sinal de que algo
específico (ângulo, gatilho, tema) fez aquele vídeo funcionar. É isso que se
disseca.

**Sinal extra — canal inteiro Outlier:** todos os vídeos recentes acima da
média, crescendo rápido em inscritos com poucos vídeos postados. Ali cada
título vira uma fonte de brecha isolada, inclusive brechas que o próprio canal
deixou passar (ex.: um único vídeo sobre "cirurgia" e nunca mais tocou no tema
— sub-nicho abandonado, pronto para virar canal próprio).

## Processo completo

1. **GARIMPAR** — achar o vídeo/canal que já validou o assunto (Outlier).
   Quanto mais recente e mais views, melhor: sinal de que está em alta agora.
2. **DISSECAR** — quebrar o formato em peças replicáveis: estrutura do título,
   ângulo, gatilho (medo/desejo/curiosidade/autoridade).
3. **MAPEAR** — listar ângulos vagos, avaliar brecha dupla, levantar
   países/idiomas com volume para o assunto.
4. **VALIDAR** — checar se o espaço está realmente livre (as 4 perguntas). Com
   muita concorrência, volta ao passo 3 e escolhe outro ângulo/país.
5. **OCUPAR** — produzir conteúdo com o formato validado, no espaço vazio.
   Chegar primeiro vale mais que copiar.

## O que o curso ainda não entregou

As aulas seguintes liberam após o período de garantia de 7 dias (~2026-09-23).
A Aula 3 menciona mas não desenvolve:

- **Ferramenta de mineração** (proxy + spoofing de localização) para acessar o
  YouTube de outros países — tratada como produto separado, fora do mini
  treinamento.
- **Análise canal a canal** (filtro por populares, comparação de views por
  período) foi mostrada na prática, mas sem detalhar a ferramenta por trás.

Ver em `../00b-alinhamento-brecha-viral.md` por que o nosso caminho técnico
para "outro país" **não** passa por proxy nem spoofing.
