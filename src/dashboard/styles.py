"""Sistema visual do dashboard: paleta, CSS e o cabeçalho padrão de cada tela.

Um único lugar para a aparência evita que cada tela reinvente cor/espaçamento
— e mantém a customização em CSS puro (sem libs de UI), consistente com a
filosofia de simplicidade de `docs/09-requisitos-nao-funcionais.md`.
"""

import streamlit as st

# Paleta "garimpo": navy escuro (autoridade/dados) + âmbar (achado, ouro).
_CSS = """
:root {
    --gc-navy: #0B1220;
    --gc-navy-2: #16233F;
    --gc-ink: #101828;
    --gc-muted: #5B6472;
    --gc-accent: #F2A93B;
    --gc-accent-dark: #C97F1C;
    --gc-accent-soft: #FFF4E0;
    --gc-border: #E7E9EE;
    --gc-card: #FFFFFF;
    --gc-radius: 14px;
}

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

/* --- barra de navegação (st.navigation position="top") ------------------ */
[data-testid="stHeader"] {
    background: #FFFFFF;
    border-bottom: 1px solid var(--gc-border);
}
[data-testid="stTopNavLink"] {
    border-radius: 999px !important;
    font-weight: 600 !important;
    transition: background 0.15s ease;
}
[data-testid="stTopNavLink"]:hover {
    background: var(--gc-accent-soft) !important;
}
[data-testid="stTopNavLink"][aria-current="page"] {
    background: var(--gc-accent-soft) !important;
}
[data-testid="stTopNavLink"][aria-current="page"] [data-testid="stMarkdownContainer"] p {
    color: var(--gc-accent-dark) !important;
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
    color: var(--gc-navy-2) !important;
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
    background: #FAFAFC;
    border-right: 1px solid var(--gc-border);
}

/* --- landing (pré-login) --------------------------------------------------- */
.gc-hero {
    background: linear-gradient(135deg, var(--gc-navy) 0%, var(--gc-navy-2) 100%);
    border-radius: 24px;
    padding: 3rem 2.5rem;
    color: #F5F6FA;
    margin-bottom: 1.75rem;
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

.gc-section-title {
    color: var(--gc-ink);
    font-weight: 800;
    font-size: 1.4rem;
    margin: 0 0 0.3rem 0;
}
.gc-section-sub {
    color: var(--gc-muted);
    margin: 0 0 1.25rem 0;
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
    background: var(--gc-card);
    border: 1px solid var(--gc-border);
    border-radius: var(--gc-radius);
    padding: 1.25rem;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04);
}
.gc-card .gc-icon {
    font-size: 1.6rem;
    display: inline-block;
    background: var(--gc-accent-soft);
    border-radius: 10px;
    padding: 0.4rem 0.55rem;
    margin-bottom: 0.6rem;
}
.gc-card h4 {
    margin: 0 0 0.35rem 0;
    color: var(--gc-ink);
    font-size: 1.02rem;
}
.gc-card p {
    margin: 0;
    color: var(--gc-muted);
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
    border: 1px solid var(--gc-border);
    background: var(--gc-card);
    border-radius: var(--gc-radius);
    padding: 1rem 1.1rem;
}
.gc-screen .gc-screen-title {
    font-weight: 700;
    color: var(--gc-ink);
    font-size: 0.95rem;
    margin-bottom: 0.25rem;
}
.gc-screen p {
    margin: 0;
    color: var(--gc-muted);
    font-size: 0.88rem;
    line-height: 1.4;
}

.gc-disclaimer {
    border: 1px solid var(--gc-border);
    border-left: 4px solid var(--gc-accent);
    background: var(--gc-accent-soft);
    border-radius: var(--gc-radius);
    padding: 1.1rem 1.3rem;
    margin-bottom: 2rem;
}
.gc-disclaimer strong { color: var(--gc-accent-dark); }
.gc-disclaimer p { margin: 0.3rem 0 0 0; color: var(--gc-ink); font-size: 0.94rem; line-height: 1.5; }

.gc-cta-heading {
    text-align: center;
    margin: 0.5rem 0 1.25rem 0;
}
.gc-cta-heading h3 { margin: 0 0 0.25rem 0; color: var(--gc-ink); }
.gc-cta-heading p { margin: 0; color: var(--gc-muted); }
"""


def inject_css() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str | None = None) -> None:
    """Cabeçalho padrão de cada tela: mesmo peso visual em todo o sistema.

    Usa st.title/st.caption de verdade (não HTML solto) para continuar
    acessível e testável — a aparência vem do CSS injetado por `inject_css`.
    """
    st.title(f"{icon}  {title}")
    if subtitle:
        st.caption(subtitle)
