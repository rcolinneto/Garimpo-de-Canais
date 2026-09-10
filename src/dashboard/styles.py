"""Sistema visual do dashboard: paleta, CSS e o cabeçalho padrão de cada tela.

Um único lugar para a aparência evita que cada tela reinvente cor/espaçamento
— e mantém a customização em CSS puro (sem libs de UI), consistente com a
filosofia de simplicidade de `docs/09-requisitos-nao-funcionais.md`.

Claro/escuro: o Streamlit já resolve isso nativamente (menu ⋮ → Settings), e é
o único jeito correto de fazer isso aqui — as tabelas do dashboard são
desenhadas em <canvas> pela grid interna dele, e só o motor de tema nativo
sabe redesenhar esses pixels (CSS não alcança canvas). O que falta ao Streamlit
fazer sozinho é recolorir os elementos que este módulo desenha por cima (cartões,
cabeçalhos, landing) — por isso `inject_css` lê `st.context.theme.type`, a API
oficial para saber qual tema está ativo, e escolhe a paleta correspondente.
"""

import streamlit as st

# Paleta "garimpo": navy escuro (autoridade/dados) + âmbar (achado, ouro).
# navy/navy-2/accent/accent-dark/radius são fixas nos dois temas (a marca não
# muda); o restante se adapta ao claro/escuro.
_CONSTANTES = """
    --gc-navy: #0B1220;
    --gc-navy-2: #16233F;
    --gc-accent: #F2A93B;
    --gc-accent-dark: #C97F1C;
    --gc-radius: 14px;
"""

_CLARO = """
    --gc-ink: #101828;
    --gc-muted: #5B6472;
    --gc-accent-soft: #FFF4E0;
    --gc-accent-text: var(--gc-accent-dark);
    --gc-border: #E7E9EE;
    --gc-card: #FFFFFF;
"""

_ESCURO = """
    --gc-ink: #F5F6FA;
    --gc-muted: #A6ADBB;
    --gc-accent-soft: rgba(242, 169, 59, 0.16);
    --gc-accent-text: var(--gc-accent);
    --gc-border: #2A3A5C;
    --gc-card: #16233F;
"""

_ESTILO_BASE = """
/* Tipografia geral: pilha de fontes do sistema, sem depender de CDN externa. */
html, body, [class*="css"] {
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* --- cabeçalhos de página (page_header) --------------------------------- */
h1 {
    color: var(--gc-ink) !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em;
}
[data-testid="stCaptionContainer"] {
    color: var(--gc-muted) !important;
    font-size: 0.95rem !important;
}

/* --- barra de navegação (st.navigation, barra lateral) ------------------- */
[data-testid="stHeader"] {
    background: var(--gc-card);
    border-bottom: 1px solid var(--gc-border);
}
[data-testid="stSidebarNav"] {
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--gc-border);
    margin-bottom: 0.75rem;
}
[data-testid="stSidebarNavLink"] {
    border-radius: 10px !important;
    font-weight: 600 !important;
    margin: 0.1rem 0;
    transition: background 0.15s ease;
}
[data-testid="stSidebarNavLink"]:hover {
    background: var(--gc-accent-soft) !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: var(--gc-accent-soft) !important;
    border-left: 3px solid var(--gc-accent);
}
[data-testid="stSidebarNavLink"][aria-current="page"] [data-testid="stMarkdownContainer"] p {
    color: var(--gc-accent-text) !important;
    font-weight: 700 !important;
}

/* --- botões (comuns, de formulário e de download) ----------------------- */
.stButton > button,
[data-testid="stFormSubmitButton"] button,
.stDownloadButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.25rem !important;
    border: 1px solid var(--gc-border) !important;
    transition: transform 0.1s ease, box-shadow 0.15s ease;
}
.stButton > button:hover,
[data-testid="stFormSubmitButton"] button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(16, 24, 40, 0.12);
}
/* Streamlit usa "primary"/"secondary" fora de formulário e
   "primaryFormSubmit"/"secondaryFormSubmit" dentro — os dois precisam do estilo. */
button[kind="primary"],
button[kind="primaryFormSubmit"] {
    background: linear-gradient(135deg, var(--gc-accent), var(--gc-accent-dark)) !important;
    border: none !important;
    color: #1A1200 !important;
}
button[kind="primary"] p,
button[kind="primaryFormSubmit"] p {
    color: #1A1200 !important;
}

/* --- métricas como cartões ------------------------------------------------ */
[data-testid="stMetric"] {
    background: var(--gc-card);
    border: 1px solid var(--gc-border);
    border-radius: var(--gc-radius);
    padding: 1rem 1.1rem;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04);
}
[data-testid="stMetricValue"] {
    /* --gc-ink (não --gc-navy-2, que é fixo e vira ilegível sobre o
       cartão escuro no tema dark, já que os dois usam a mesma cor). */
    color: var(--gc-ink) !important;
}

/* --- formulários como cartões (login, cadastro/edição de nicho) --------- */
[data-testid="stForm"] {
    background: var(--gc-card);
    border: 1px solid var(--gc-border);
    border-radius: 18px;
    padding: 1.5rem 1.5rem 0.75rem;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04);
}

/* --- tabelas -------------------------------------------------------------- */
[data-testid="stDataFrame"] {
    border: 1px solid var(--gc-border);
    border-radius: var(--gc-radius);
    overflow: hidden;
}

/* --- avisos (info/warning/success/error) ---------------------------------- */
[data-testid="stAlert"] {
    border-radius: var(--gc-radius) !important;
}

/* --- barra lateral ---------------------------------------------------------- */
[data-testid="stSidebar"] {
    border-right: 1px solid var(--gc-border);
}

/* --- landing (pré-login) --------------------------------------------------- */
/* Sempre escura, nos dois temas — é a marca (inspirada em fitagenda-amber.
   vercel.app), não a interface de trabalho, então não segue claro/escuro.
   Paleta fixa própria (--gc-land-*) em vez de --gc-ink/--gc-card, que mudam
   com o tema — essas classes só existem aqui, nunca no app autenticado. */
:root {
    --gc-land-bg: #0A090C;
    --gc-land-card: #17161C;
    --gc-land-border: rgba(255, 255, 255, 0.09);
    --gc-land-text: #F5F4F2;
    --gc-land-muted: #9C9BA3;
}

.gc-landing-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0 1.75rem 0;
}
.gc-landing-nav .gc-wordmark { margin: 0; }
.gc-landing-nav a {
    color: var(--gc-land-text);
    text-decoration: none;
    font-size: 0.88rem;
    font-weight: 600;
    margin-left: 1.75rem;
}
.gc-landing-nav a:hover { color: var(--gc-accent); }
.gc-landing-nav .gc-nav-cta {
    background: var(--gc-accent);
    color: #1A1200;
    padding: 0.45rem 1.1rem;
    border-radius: 999px;
}
.gc-landing-nav .gc-nav-cta:hover { color: #1A1200; opacity: 0.9; }

.gc-hero {
    background: linear-gradient(160deg, var(--gc-navy) 0%, #050508 100%);
    border: 1px solid var(--gc-land-border);
    border-radius: 24px;
    padding: 3rem 2.5rem;
    color: var(--gc-land-text);
    margin-bottom: 1.5rem;
}
.gc-wordmark {
    color: var(--gc-accent);
    font-weight: 800;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
    margin: 0 0 0.9rem 0;
}
.gc-badge {
    display: inline-block;
    background: rgba(242, 169, 59, 0.15);
    color: var(--gc-accent);
    border: 1px solid rgba(242, 169, 59, 0.35);
    border-radius: 999px;
    padding: 0.3rem 0.9rem;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 1rem;
}
.gc-hero h1 {
    color: #FFFFFF !important;
    font-size: 2.6rem !important;
    line-height: 1.15;
    margin: 0 0 0.75rem 0;
}
.gc-hero .gc-accent-word { color: var(--gc-accent); }
.gc-hero p {
    color: #C7CCDA;
    font-size: 1.12rem;
    max-width: 620px;
    line-height: 1.55;
    margin: 0;
}

/* --- tira de fatos técnicos (equivalente neutro à "prova social") ------- */
.gc-facts {
    display: flex;
    flex-wrap: wrap;
    gap: 2.5rem;
    padding: 0 0.25rem 2rem 0.25rem;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid var(--gc-land-border);
}
.gc-fact-value {
    color: var(--gc-accent);
    font-weight: 800;
    font-size: 1.3rem;
    display: block;
}
.gc-fact-label {
    color: var(--gc-land-muted);
    font-size: 0.82rem;
}

/* --- ticker/faixa de sinais monitorados ---------------------------------- */
.gc-ticker {
    overflow: hidden;
    white-space: nowrap;
    border-top: 1px solid var(--gc-land-border);
    border-bottom: 1px solid var(--gc-land-border);
    padding: 0.8rem 0;
    margin: 0 0 2.25rem 0;
    -webkit-mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent);
    mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent);
}
.gc-ticker-track {
    display: inline-block;
    animation: gc-ticker-scroll 32s linear infinite;
}
.gc-ticker-item {
    display: inline-block;
    color: var(--gc-land-muted);
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.gc-ticker-item .gc-dot { color: var(--gc-accent); margin: 0 1.4rem; }
@keyframes gc-ticker-scroll {
    from { transform: translateX(0); }
    to { transform: translateX(-50%); }
}

.gc-section-title {
    color: var(--gc-land-text);
    font-weight: 800;
    font-size: 1.4rem;
    margin: 0 0 0.3rem 0;
}
.gc-section-sub {
    color: var(--gc-land-muted);
    margin: 0 0 1.25rem 0;
}
.gc-eyebrow {
    color: var(--gc-accent);
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 0.4rem 0;
}

/* --- contexto (por que isso existe) -------------------------------------- */
.gc-context {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 2rem;
    margin-bottom: 2.5rem;
    align-items: start;
}
@media (max-width: 900px) {
    .gc-context { grid-template-columns: 1fr; }
}
.gc-context h2 {
    color: var(--gc-land-text);
    font-size: 1.7rem;
    font-weight: 800;
    line-height: 1.3;
    margin: 0;
}
.gc-context .gc-muted-strong { color: var(--gc-land-muted); }
.gc-context-list { display: flex; flex-direction: column; gap: 0.6rem; }
.gc-context-item {
    background: var(--gc-land-card);
    border: 1px solid var(--gc-land-border);
    border-radius: 12px;
    padding: 0.8rem 1rem;
    color: #D7D6DC;
    font-size: 0.92rem;
}

.gc-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.75rem;
}
@media (max-width: 900px) {
    .gc-grid { grid-template-columns: repeat(2, 1fr); }
}
.gc-card {
    background: var(--gc-land-card);
    border: 1px solid var(--gc-land-border);
    border-radius: var(--gc-radius);
    padding: 1.25rem;
}
.gc-card .gc-icon {
    font-size: 1.6rem;
    display: inline-block;
    background: rgba(242, 169, 59, 0.14);
    border-radius: 10px;
    padding: 0.4rem 0.55rem;
    margin-bottom: 0.6rem;
}
.gc-card h4 {
    margin: 0 0 0.35rem 0;
    color: var(--gc-land-text);
    font-size: 1.02rem;
}
.gc-card p {
    margin: 0;
    color: var(--gc-land-muted);
    font-size: 0.92rem;
    line-height: 1.45;
}

/* --- como funciona (passos numerados) ------------------------------------ */
.gc-steps {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.5rem;
    margin-bottom: 2.5rem;
}
@media (max-width: 900px) {
    .gc-steps { grid-template-columns: 1fr; }
}
.gc-step-number {
    color: var(--gc-accent);
    font-weight: 800;
    font-size: 1.6rem;
    display: block;
    margin-bottom: 0.4rem;
}
.gc-step h4 {
    color: var(--gc-land-text);
    margin: 0 0 0.35rem 0;
    font-size: 1.02rem;
}
.gc-step p {
    color: var(--gc-land-muted);
    margin: 0;
    font-size: 0.92rem;
    line-height: 1.45;
}

.gc-screens {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
    margin-bottom: 1.75rem;
}
.gc-screen {
    border: 1px solid var(--gc-land-border);
    background: var(--gc-land-card);
    border-radius: var(--gc-radius);
    padding: 1rem 1.1rem;
}
.gc-screen .gc-screen-title {
    font-weight: 700;
    color: var(--gc-land-text);
    font-size: 0.95rem;
    margin-bottom: 0.25rem;
}
.gc-screen p {
    margin: 0;
    color: var(--gc-land-muted);
    font-size: 0.88rem;
    line-height: 1.4;
}

.gc-disclaimer {
    border: 1px solid var(--gc-land-border);
    border-left: 4px solid var(--gc-accent);
    background: var(--gc-land-card);
    border-radius: var(--gc-radius);
    padding: 1.1rem 1.3rem;
    margin-bottom: 2rem;
}
.gc-disclaimer strong { color: var(--gc-accent); }
.gc-disclaimer p { margin: 0.3rem 0 0 0; color: #D7D6DC; font-size: 0.94rem; line-height: 1.5; }

/* --- perguntas frequentes (st.expander dentro de st.container(key=...)) --
   st.expander é um widget nativo, não aninha dentro do HTML que a landing
   injeta via st.markdown — por isso o escopo usa a classe st-key-<key> que
   o próprio Streamlit gera para um st.container(key=...), em vez de tentar
   um wrapper de div que não existiria de verdade no DOM. Sem esse escopo,
   estilizar [data-testid="stExpander"] direto afetaria os expanders das
   Telas 2 e 3 também. */
.st-key-gc_faq [data-testid="stExpander"] {
    background: var(--gc-land-card);
    border: 1px solid var(--gc-land-border);
    border-radius: 12px;
    margin-bottom: 0.6rem;
}
.st-key-gc_faq [data-testid="stExpander"] summary {
    color: var(--gc-land-text) !important;
    font-weight: 600;
}
.st-key-gc_faq [data-testid="stExpander"] p {
    color: var(--gc-land-muted) !important;
}

.gc-cta-heading {
    text-align: center;
    margin: 0.5rem 0 1.25rem 0;
}
.gc-cta-heading h3 { margin: 0 0 0.25rem 0; color: var(--gc-land-text); }
.gc-cta-heading p { margin: 0; color: var(--gc-land-muted); }

/* Cartão do login escurecido para combinar com o resto da landing — escopado
   por st.container(key="gc_login") porque st.form() não gera uma classe
   st-key-<key> própria (confirmado inspecionando o DOM real; só
   st.container(key=...) gera). O campo de texto em si mantém o estilo nativo
   claro do Streamlit (não dá pra forçar escuro em widgets nativos, ver topo
   do arquivo) — funciona bem como uma "pílula" clara sobre o cartão escuro. */
.st-key-gc_login [data-testid="stForm"] {
    background: var(--gc-land-card) !important;
    border-color: var(--gc-land-border) !important;
}
.st-key-gc_login label {
    color: var(--gc-land-text) !important;
}

.gc-landing-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 1.5rem;
    margin-top: 1rem;
    border-top: 1px solid var(--gc-land-border);
    color: var(--gc-land-muted);
    font-size: 0.82rem;
}
"""


def _build_css(dark: bool) -> str:
    paleta = _ESCURO if dark else _CLARO
    return f":root {{{_CONSTANTES}{paleta}}}\n{_ESTILO_BASE}"


_CSS_CANVAS_LANDING = """
/* Fundo do próprio Streamlit (fora do que este módulo desenha) forçado
   escuro só na landing — as páginas autenticadas continuam seguindo o tema
   nativo claro/escuro do viewer, então isso nunca entra nesse CSS quando
   landing=False. */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.stApp {
    background: var(--gc-land-bg) !important;
}
[data-testid="stHeader"] {
    background: var(--gc-land-bg) !important;
    border-bottom: 1px solid var(--gc-land-border) !important;
}
"""


def inject_css(landing: bool = False) -> None:
    """Injeta o CSS na paleta certa para o tema ativo no navegador.

    `st.context.theme.type` é a API oficial para ler claro/escuro (inferida do
    fundo do app). A própria documentação avisa que pode ficar desatualizada
    por um instante logo após o usuário trocar de tema — é inofensivo aqui:
    a próxima interação já corrige, e nada quebra visualmente nesse meio-tempo.

    `landing=True` também escurece o canvas do próprio Streamlit (por trás do
    que as classes .gc-* desenham) — só usado na tela pré-login, que é sempre
    escura independente do tema do viewer (ver seção "landing" acima).
    """
    escuro = st.context.theme.type == "dark"
    css = _build_css(escuro)
    if landing:
        css += _CSS_CANVAS_LANDING
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str | None = None) -> None:
    """Cabeçalho padrão de cada tela: mesmo peso visual em todo o sistema.

    Usa st.title/st.caption de verdade (não HTML solto) para continuar
    acessível e testável — a aparência vem do CSS injetado por `inject_css`.
    """
    st.title(f"{icon}  {title}")
    if subtitle:
        st.caption(subtitle)
