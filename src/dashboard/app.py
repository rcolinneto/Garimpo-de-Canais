"""Dashboard do Garimpo de Canais (docs/06-dashboard.md).

Consome exclusivamente a API interna — nenhuma consulta ao banco sai daqui,
conforme `docs/02-arquitetura.md`.

Execução: streamlit run src/dashboard/app.py
"""

import hmac
import html
import threading

import pandas as pd
import streamlit as st

from src.config.settings import settings
from src.dashboard import api_client
from src.dashboard.api_client import ApiError
from src.dashboard.styles import eyebrow, inject_css, page_header

# Taxonomia de docs/05-motor-monetizacao-e-score.md, usada no filtro da Tela 2.
TIPOS_DE_SINAL = [
    "link_afiliado",
    "loja_propria",
    "infoproduto",
    "comunidade_paga",
    "link_agregador",
    "patrocinio_mencionado",
    "elegivel_parceria_plataforma",
]

# Termos que passam na faixa animada da landing (docs/05) — só rótulos legíveis
# do que o sistema já reconhece, sem número de negócio nenhum.
TERMOS_TICKER = [
    "Link de afiliado",
    "Loja própria",
    "Infoproduto",
    "Comunidade paga",
    "Link agregador",
    "Patrocínio mencionado",
    "Elegibilidade ao YouTube Partner Program",
    "Crescimento de inscritos",
    "Viralidade do nicho",
]

# Perguntas frequentes da landing — conteúdo explicativo, não objeção de venda.
FAQ = [
    (
        "O score reflete a receita real do canal?",
        "Não. É uma estimativa por evidência indireta — nenhuma ferramenta de mercado "
        "tem acesso à receita real de um canal de terceiros. O score prioriza o que "
        "vale investigar, não afirma quanto alguém fatura.",
    ),
    (
        "De onde vêm os dados?",
        "Da YouTube Data API v3, oficial e gratuita dentro da cota diária. Não há "
        "scraping nem coleta fora dos termos de uso da plataforma.",
    ),
    (
        "Com que frequência os dados são atualizados?",
        "Um snapshot diário automático de todos os canais monitorados, mais a opção "
        "de disparar uma busca manual por um nicho específico a qualquer momento, "
        "direto na tela 'Canais Descobertos'.",
    ),
    (
        "Os nichos são escolhidos pelo sistema?",
        "Não — são cadastrados manualmente na tela 'Configuração de Nichos'. O "
        "sistema garimpa dentro dos nichos que você definir, não decide nichos sozinho.",
    ),
    (
        "O que acontece se um canal sai do ar?",
        "O histórico já coletado permanece; o canal só é marcado como removido. "
        "Nada é apagado.",
    ),
]


# Rótulos legíveis para a taxonomia de sinais de monetização (docs/05) — a API
# devolve o slug técnico em snake_case; a tela mostra o que faz sentido pra
# quem não escreveu o código.
SIGNAL_LABELS = {
    "link_afiliado": "Link de afiliado",
    "loja_propria": "Loja própria",
    "infoproduto": "Infoproduto",
    "comunidade_paga": "Comunidade paga",
    "link_agregador": "Link agregador",
    "patrocinio_mencionado": "Patrocínio mencionado",
    "elegivel_parceria_plataforma": "Elegível à parceria (YPP)",
}


def rotulo_sinal(slug: str) -> str:
    return SIGNAL_LABELS.get(slug, slug)


# Paleta dos gráficos — consistente com a marca, no lugar do azul padrão do
# Vega-Lite. Usada na ordem: principal, acento, e dois tons de apoio para
# quando um gráfico tem vários componentes (ex.: score total + seus 3 fatores).
COR_PRIMARIA = "#16233F"
COR_ACENTO = "#F2A93B"
COR_SECUNDARIA = "#2E7D6B"
COR_TERCIARIA = "#A9598B"


# --- autenticação -----------------------------------------------------------


def _apresentacao() -> None:
    """Landing page de apresentação para quem chega sem contexto.

    Layout inspirado em fitagenda-amber.vercel.app (tema escuro, ticker de
    recursos, passos numerados, FAQ) — adaptado para explicar, não vender:
    sem agitação de dor, sem preço, sem urgência artificial. De propósito não
    mostra nenhum número real do negócio: o dashboard fica atrás de senha
    justamente porque expõe análise de mercado (docs/09), e esta tela é
    pública para quem alcança a URL. É conteúdo estático (HTML/CSS embutido)
    — não faz nenhuma chamada à API, então não tem como vazar dado nenhum.
    """
    st.markdown(
        """
        <div class="gc-landing-nav">
          <p class="gc-wordmark">📡 GARIMPO DE CANAIS</p>
          <div>
            <a href="#como-funciona">Como funciona</a>
            <a href="#perguntas">Perguntas</a>
            <a href="#acessar" class="gc-nav-cta">Acessar →</a>
          </div>
        </div>
        <div class="gc-hero">
          <span class="gc-badge">🛰️ Coleta automática · YouTube Data API v3</span>
          <h1>Um radar que acompanha canais do <span class="gc-accent-word">YouTube</span>
              em crescimento, todos os dias, sozinho</h1>
          <p>O sistema procura canais pequenos que estão crescendo dentro dos nichos
             configurados e verifica quais já dão sinais de estar sendo monetizados —
             sempre guardando a evidência exata de cada achado, para conferência manual
             antes de qualquer decisão.</p>
        </div>

        <div class="gc-facts">
          <div><span class="gc-fact-value">YouTube Data API v3</span><span class="gc-fact-label">fonte dos dados, sem scraping</span></div>
          <div><span class="gc-fact-value">Diária</span><span class="gc-fact-label">frequência da coleta</span></div>
          <div><span class="gc-fact-value">3 componentes</span><span class="gc-fact-label">formam o score de priorização</span></div>
          <div><span class="gc-fact-value">7 tipos</span><span class="gc-fact-label">de sinal de monetização reconhecidos</span></div>
        </div>

        <div class="gc-ticker"><div class="gc-ticker-track">
        """
        + "".join(
            f'<span class="gc-ticker-item">{termo}<span class="gc-dot">•</span></span>'
            for termo in TERMOS_TICKER * 2
        )
        + """
        </div></div>

        <div class="gc-context">
          <h2>Nichos viram centenas de canais novos por semana —
              <span class="gc-muted-strong">olhar cada um manualmente não escala.</span></h2>
          <div class="gc-context-list">
            <div class="gc-context-item">Sinais de monetização ficam escondidos na descrição do canal e dos vídeos, não na aba "Sobre".</div>
            <div class="gc-context-item">Crescimento real exige comparar ao longo do tempo — um único snapshot não mostra tendência.</div>
            <div class="gc-context-item">Um nicho "aquecido" é vários canais crescendo juntos, não um vídeo viral isolado.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="gc-eyebrow">O que ele faz</p>'
        '<p class="gc-section-title">Quatro etapas que rodam sozinhas</p>'
        '<p class="gc-section-sub">Todos os dias, sem intervenção manual.</p>',
        unsafe_allow_html=True,
    )
    blocos = [
        ("🔎", "Descobre", "Busca canais novos nos nichos configurados e só cadastra os que ainda são pequenos e têm vídeos recentes acima do próprio tamanho — não recadastra quem já estourou."),
        ("📈", "Acompanha", "Guarda um retrato das métricas de cada canal todo dia, formando o histórico que mostra quem está realmente subindo, não só o número de hoje."),
        ("💰", "Detecta monetização", "Procura links de afiliado, infoprodutos, lojas e comunidades pagas nas descrições — e guarda a evidência exata de cada achado."),
        ("🎯", "Prioriza", "Combina crescimento, monetização e aquecimento do nicho em um único score, para saber o que vale olhar primeiro."),
    ]
    st.markdown(
        '<div class="gc-grid">'
        + "".join(
            f'<div class="gc-card"><span class="gc-icon">{icone}</span>'
            f"<h4>{titulo}</h4><p>{texto}</p></div>"
            for icone, titulo, texto in blocos
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div id="como-funciona"></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="gc-eyebrow">Por baixo do capô</p>'
        '<p class="gc-section-title">Como funciona</p>',
        unsafe_allow_html=True,
    )
    passos = [
        ("01", "Descoberta", "Busca vídeos recentes nas palavras-chave de cada nicho e verifica se o canal por trás ainda é pequeno o suficiente para ser uma descoberta, não um recadastro."),
        ("02", "Snapshot diário", "Registra inscritos, views e engajamento de cada canal já conhecido, formando o histórico que sustenta o cálculo de crescimento."),
        ("03", "Enriquecimento", "Varre descrições em busca de sinais de monetização e recalcula o score de cada canal com o que mudou no dia."),
    ]
    st.markdown(
        '<div class="gc-steps">'
        + "".join(
            f'<div class="gc-step"><span class="gc-step-number">{num}</span>'
            f"<h4>{titulo}</h4><p>{texto}</p></div>"
            for num, titulo, texto in passos
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="gc-eyebrow">Dentro do dashboard</p>'
        '<p class="gc-section-title">O que você encontra lá dentro</p>'
        '<p class="gc-section-sub">Cinco telas, cada uma resolvendo uma pergunta diferente.</p>',
        unsafe_allow_html=True,
    )
    telas = [
        ("Visão Geral", "Quais nichos estão mais aquecidos agora, com histórico de evolução."),
        ("Canais Descobertos", "A tabela de trabalho: filtra por nicho, tamanho, crescimento e sinais de monetização; exporta para CSV."),
        ("Detalhe do Canal", "Gráficos de inscritos, views e score ao longo do tempo, e a evidência de cada sinal encontrado."),
        ("Configuração de Nichos", "Cadastre ou pause nichos sem depender de ninguém — o histórico já coletado nunca se perde."),
        ("Alertas", "Avisa por e-mail quando um canal cruza o score que você definir como relevante."),
    ]
    st.markdown(
        '<div class="gc-screens">'
        + "".join(
            f'<div class="gc-screen"><div class="gc-screen-title">{nome}</div><p>{texto}</p></div>'
            for nome, texto in telas
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="gc-disclaimer">
          <strong>⚠️ Como isso funciona de verdade</strong>
          <p>O sistema <strong>estima</strong> monetização por evidência indireta — um link
             de pagamento na descrição, um e-book anunciado. Ele nunca sabe quanto um canal
             de terceiros realmente fatura, e nenhuma ferramenta do mercado sabe isso. Por
             isso cada sinal vem com a evidência exata que o gerou, para conferência manual
             antes de qualquer decisão.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div id="perguntas"></div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="gc-eyebrow">Dúvidas comuns</p>'
        '<p class="gc-section-title">Perguntas frequentes</p>',
        unsafe_allow_html=True,
    )
    with st.container(key="gc_faq"):
        for pergunta, resposta in FAQ:
            with st.expander(pergunta):
                st.write(resposta)

    st.markdown('<div id="acessar"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="gc-cta-heading"><h3>Acessar o dashboard</h3>'
        "<p>Entre com a senha da equipe.</p></div>",
        unsafe_allow_html=True,
    )


def autenticar() -> bool:
    """Senha compartilhada via variável de ambiente (docs/06, seção Autenticação)."""
    if st.session_state.get("autenticado"):
        return True

    _apresentacao()

    if not settings.dashboard_password:
        # Falha fechada: o dashboard expõe análise de mercado da empresa, então
        # ficar aberto por falta de configuração seria pior que não subir.
        st.error(
            "DASHBOARD_PASSWORD não configurada. Defina a variável de ambiente "
            "para liberar o acesso ao dashboard."
        )
        return False

    with st.container(key="gc_login"):
        _, meio, _ = st.columns([1, 1.2, 1])
        with meio.form("login"):
            senha = st.text_input("Senha", type="password", placeholder="Senha da equipe")
            if st.form_submit_button(
                "Entrar no dashboard →", type="primary", use_container_width=True
            ):
                if hmac.compare_digest(senha, settings.dashboard_password):
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")

    st.markdown(
        '<div class="gc-landing-footer">'
        "<span>📡 Garimpo de Canais</span>"
        "<span>Coleta automática via YouTube Data API v3</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    return False


# --- helpers ----------------------------------------------------------------


def carregar(funcao, *args, **kwargs):
    """Executa uma chamada de API mostrando o erro na tela em vez de estourar."""
    try:
        # A mensagem já explica a espera longa de propósito: na hospedagem
        # gratuita o servidor desliga quando fica ocioso, e a primeira abertura
        # do dia espera ele subir. Sem esse aviso a tela parece travada — foi
        # exatamente assim que o problema chegou como "não abre nenhuma aba".
        with st.spinner(
            "Carregando dados… se o servidor estiver ocioso, a primeira "
            "abertura pode levar até 1 minuto enquanto ele acorda."
        ):
            return funcao(*args, **kwargs)
    except ApiError as erro:
        st.error(str(erro))
        return None


def formatar_canais(itens: list[dict]) -> pd.DataFrame:
    """Colunas da Tela 2, na ordem descrita em docs/06."""
    return pd.DataFrame(
        [
            {
                "Canal": item["display_name"],
                "Link": item["url"],
                "Nicho": item["niche_name"] or "—",
                "Inscritos": item["subscriber_count"] if item["subscriber_count"] is not None else "oculto",
                # "—" e não None: sem histórico de 7/30 dias ainda para comparar
                # (canal recém-descoberto), não é um erro nem um zero.
                "Cresc. 7d (%)": _arredondar(item["crescimento_7d"]),
                "Cresc. 30d (%)": _arredondar(item["crescimento_30d"]),
                "Sinais": ", ".join(rotulo_sinal(s) for s in item["sinais_monetizacao"]) or "—",
                "Score": _arredondar(item["total_score"]),
                "Descoberto em": (item["discovered_at"] or "")[:10],
                "id": item["id"],
            }
            for item in itens
        ]
    )


def _arredondar(valor, casas: int = 2):
    """Arredonda para exibição; None/valor ausente vira "—", nunca a string "None"."""
    return round(valor, casas) if isinstance(valor, (int, float)) else "—"


def selecionar_canal(itens: list[dict], chave: str) -> int | None:
    """Selectbox de canais, respeitando o que veio selecionado da Tela 2."""
    if not itens:
        return None
    opcoes = {f"{item['display_name']} ({item['subscriber_count'] or '?'} inscritos)": item["id"] for item in itens}
    ids = list(opcoes.values())
    preferido = st.session_state.get("canal_selecionado")
    indice = ids.index(preferido) if preferido in ids else 0
    rotulo = st.selectbox("Canal", list(opcoes.keys()), index=indice, key=chave)
    return opcoes[rotulo]


# --- Tela 1 -----------------------------------------------------------------


def tela_visao_geral() -> None:
    page_header(
        "📡",
        "Visão Geral",
        "Em 10 segundos: o que está bombando agora, por nicho monitorado.",
    )

    nichos = carregar(api_client.ranking_de_nichos)
    if nichos is None:
        return
    if not nichos:
        st.info("Nenhum nicho cadastrado ainda. Use a tela 'Configuração de Nichos'.")
        return

    total_canais = sum(nicho["canais_ativos"] for nicho in nichos)
    novos = sum(nicho["novos_esta_semana"] for nicho in nichos)
    colunas = st.columns(3)
    colunas[0].metric("Nichos monitorados", len(nichos))
    colunas[1].metric("Canais ativos", total_canais)
    colunas[2].metric("Novos esta semana", novos)

    st.divider()
    eyebrow("Ranking")
    st.subheader("Nichos por viralidade")
    st.caption(
        "Viralidade = crescimento médio dos canais ativos daquele nicho. Um nicho onde "
        "vários canais crescem ao mesmo tempo é mais interessante que um canal isolado."
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Nicho": nicho["name"],
                    "Ativo": "sim" if nicho["active"] else "pausado",
                    "Canais ativos": nicho["canais_ativos"],
                    "Novos esta semana": nicho["novos_esta_semana"],
                    "Viralidade do nicho": _arredondar(nicho["niche_virality_score"]),
                    "Score médio": _arredondar(nicho["total_score_medio"]),
                    "Última descoberta": (nicho["last_discovery_at"] or "—")[:10],
                }
                for nicho in nichos
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    eyebrow("Tendência")
    st.subheader("Evolução da viralidade")
    por_nome = {nicho["name"]: nicho["niche_id"] for nicho in nichos}
    escolhido = st.selectbox("Nicho", list(por_nome.keys()))
    dias = st.radio("Janela", [30, 90], horizontal=True, format_func=lambda d: f"{d} dias")

    historico = carregar(api_client.historico_do_nicho, por_nome[escolhido], dias)
    if not historico:
        st.info("Ainda não há histórico de score suficiente para desenhar o gráfico.")
        return
    serie = pd.DataFrame(historico)
    serie["dia"] = pd.to_datetime(serie["dia"])
    st.line_chart(serie.set_index("dia")["niche_virality_score"], color=COR_PRIMARIA)


# --- Tela 2 -----------------------------------------------------------------


def tela_canais() -> None:
    page_header(
        "🔎",
        "Canais Descobertos",
        "A tabela de trabalho — refine pelos filtros ao lado e ordene por score.",
    )

    nichos = carregar(api_client.ranking_de_nichos) or []
    opcoes_nicho = {"Todos": None} | {nicho["name"]: nicho["niche_id"] for nicho in nichos}

    with st.expander("🛰️ Buscar novos canais agora no YouTube"):
        st.caption(
            "Dispara uma busca de verdade na API do YouTube para o nicho escolhido, sem "
            "esperar o job agendado (roda sozinho às 3h e 5h). Consome cota real da API — "
            "cerca de 100 unidades de busca mais ~3 por candidato analisado — e pode levar "
            "de dezenas de segundos a um par de minutos."
        )
        nichos_ativos = {nicho["name"]: nicho["niche_id"] for nicho in nichos if nicho["active"]}
        if not nichos_ativos:
            st.info(
                "Nenhum nicho ativo cadastrado ainda. Cadastre um na tela "
                "'Configuração de Nichos' para poder buscar."
            )
        else:
            nicho_busca = st.selectbox(
                "Nicho", list(nichos_ativos.keys()), key="nicho_busca_agora"
            )
            if st.button("🔎 Buscar agora", type="primary"):
                with st.spinner(f"Buscando '{nicho_busca}' no YouTube — pode demorar um pouco..."):
                    resultado = carregar(
                        api_client.buscar_nicho_agora, nichos_ativos[nicho_busca]
                    )
                if resultado is not None:
                    if resultado["status"] == "failed":
                        st.error(f"A busca falhou: {resultado['error_message']}")
                    elif resultado["canais_novos"] == 0:
                        st.info(
                            f"Busca concluída ({resultado['api_units_consumed']} unidades de "
                            "cota) — nenhum canal novo encontrado desta vez."
                        )
                    else:
                        st.success(
                            f"{resultado['canais_novos']} canal(is) novo(s) — "
                            f"{', '.join(resultado['novos_canais'])} "
                            f"({resultado['api_units_consumed']} unidades de cota). Já aparecem "
                            "na tabela abaixo."
                        )
                    if resultado is not None and resultado["status"] == "partial":
                        st.warning(
                            "A cota do dia estourou no meio da busca — o que já tinha sido "
                            "encontrado até então foi salvo."
                        )

    with st.sidebar:
        st.header("🔧 Filtros")
        st.caption("Combine quantos quiser; a lista se atualiza sozinha.")
        nicho = st.selectbox("Nicho", list(opcoes_nicho.keys()))
        min_subs, max_subs = st.columns(2)
        minimo_inscritos = min_subs.number_input("Inscritos (mín.)", min_value=0, value=0, step=100)
        maximo_inscritos = max_subs.number_input("Inscritos (máx.)", min_value=0, value=0, step=1000)
        crescimento = st.number_input(
            "Crescimento mín. 7d (%)",
            value=0.0,
            step=1.0,
            help="Variação de inscritos entre o snapshot de hoje e o de 7 dias atrás.",
        )
        score_minimo = st.number_input(
            "Score mínimo",
            min_value=0.0,
            value=0.0,
            step=1.0,
            help="Combina crescimento, monetização e aquecimento do nicho num só número — quanto maior, mais prioritário.",
        )
        sinais = st.multiselect(
            "Sinais de monetização",
            TIPOS_DE_SINAL,
            format_func=rotulo_sinal,
            help="Mostra só canais com pelo menos um destes sinais detectado nos últimos 30 dias.",
        )
        descobertos_em = st.selectbox(
            "Descobertos nos últimos",
            [None, 7, 15, 30, 90],
            format_func=lambda d: "qualquer data" if d is None else f"{d} dias",
            help="Filtra pela data em que o canal entrou no sistema, não pela data de criação dele no YouTube.",
        )
        limite = st.slider("Máximo de canais", min_value=10, max_value=200, value=50, step=10)

    dados = carregar(
        api_client.listar_canais,
        niche_id=opcoes_nicho[nicho],
        min_subscribers=minimo_inscritos or None,
        max_subscribers=maximo_inscritos or None,
        min_growth=crescimento or None,
        min_score=score_minimo or None,
        signal_types=sinais or None,
        discovered_since_days=descobertos_em,
        limit=limite,
    )
    if dados is None:
        return

    itens = dados["items"]
    eyebrow(f"{len(itens)} de {dados['total']} canais no filtro atual")
    st.caption("Ordenados por score — o mais promissor primeiro.")
    if not itens:
        st.info("Nenhum canal bate com esses filtros.")
        return

    tabela = formatar_canais(itens)
    st.dataframe(
        tabela.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir")},
    )

    st.download_button(
        "⬇️ Exportar CSV da visão atual",
        data=tabela.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
        file_name="canais_garimpados.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Ver um canal em detalhe")
    st.caption("Escolha um canal e abra a página 'Detalhe do Canal' no menu acima.")
    escolhido = selecionar_canal(itens, "canal_tela2")
    if st.button("Abrir este canal →", type="primary"):
        st.session_state["canal_selecionado"] = escolhido
        st.success("Canal selecionado — abra 'Detalhe do Canal' no menu do topo.")


# --- Tela 3 -----------------------------------------------------------------


def tela_detalhe() -> None:
    page_header(
        "📈",
        "Detalhe do Canal",
        "Evolução ao longo do tempo e a evidência por trás de cada sinal de monetização.",
    )

    dados = carregar(api_client.listar_canais, limit=200)
    if dados is None:
        return
    itens = dados["items"]
    if not itens:
        st.info("Nenhum canal descoberto ainda.")
        return

    channel_id = selecionar_canal(itens, "canal_tela3")
    canal = carregar(api_client.detalhar_canal, channel_id)
    if canal is None:
        return

    st.header(canal["display_name"] or canal["youtube_channel_id"])
    cabecalho = []
    if canal["niche_name"]:
        cabecalho.append(f'<span class="gc-badge-pill">{html.escape(canal["niche_name"])}</span>')
    if canal["url"]:
        # Construída pelo nosso próprio backend (_channel_url), mas escapamos
        # mesmo assim — sem confiar em "isso nunca teria caractere especial".
        cabecalho.append(
            f'🔗 <a href="{html.escape(canal["url"])}" target="_blank">Abrir canal no YouTube</a>'
        )
    if cabecalho:
        st.markdown(
            f'<div style="margin: 0.2rem 0 1rem 0;">{"&nbsp;&nbsp;".join(cabecalho)}</div>',
            unsafe_allow_html=True,
        )

    colunas = st.columns(3)
    colunas[0].metric("Inscritos", canal["subscriber_count"] or "oculto")
    colunas[1].metric("Score total", _arredondar(canal["total_score"]))
    colunas[2].metric("Descoberto em", (canal["discovered_at"] or "")[:10])

    historico = carregar(api_client.historico_canal, channel_id)
    if historico:
        snapshots = pd.DataFrame(historico["snapshots"])
        if not snapshots.empty:
            snapshots["collected_at"] = pd.to_datetime(snapshots["collected_at"])
            snapshots = snapshots.set_index("collected_at")
            # Dois gráficos em vez de um: inscritos e views têm escalas muito
            # diferentes, e juntos achatariam a linha de inscritos.
            st.divider()
            eyebrow("Histórico")
            st.subheader("Evolução de inscritos")
            st.line_chart(snapshots["subscriber_count"], color=COR_PRIMARIA)
            st.subheader("Evolução de views totais")
            st.line_chart(snapshots["total_view_count"], color=COR_PRIMARIA)

        scores = pd.DataFrame(historico["scores"])
        if not scores.empty:
            scores["calculated_at"] = pd.to_datetime(scores["calculated_at"])
            st.subheader("Evolução do score e seus componentes")
            st.caption("Score total = crescimento + monetização + aquecimento do nicho, já com os pesos aplicados.")
            componentes = scores.set_index("calculated_at")[
                ["total_score", "growth_score", "monetization_score", "niche_virality_score"]
            ].rename(
                columns={
                    "total_score": "Score total",
                    "growth_score": "Crescimento",
                    "monetization_score": "Monetização",
                    "niche_virality_score": "Aquecimento do nicho",
                }
            )
            st.line_chart(componentes, color=[COR_PRIMARIA, COR_ACENTO, COR_SECUNDARIA, COR_TERCIARIA])

    st.divider()
    eyebrow("Prova")
    st.subheader("Sinais de monetização detectados")
    if canal["sinais"]:
        st.caption("A evidência é o que motivou cada detecção — confira antes de agir sobre ela.")
        st.markdown(
            '<div class="gc-signal-grid">'
            + "".join(
                '<div class="gc-signal-card">'
                '<div class="gc-signal-card-head">'
                f'<span class="gc-signal-type">{html.escape(rotulo_sinal(sinal["signal_type"]))}</span>'
                f'<span class="gc-signal-meta">confiança {_arredondar(sinal["confidence"])} · '
                f'{(sinal["detected_at"] or "")[:10]}</span>'
                "</div>"
                # evidence vem de descrições reais do YouTube (texto de terceiros) —
                # sempre escapado antes de entrar num bloco unsafe_allow_html.
                f'<div class="gc-signal-evidence">{html.escape(sinal["evidence"] or "—")}</div>'
                "</div>"
                for sinal in canal["sinais"]
            )
            + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Nenhum sinal de monetização detectado para este canal até agora.")

    if canal["score_breakdown"]:
        with st.expander("Por que este canal tem esse score?"):
            st.json(canal["score_breakdown"])

    st.divider()
    eyebrow("Conteúdo recente")
    st.subheader("Últimos vídeos coletados")
    if canal["ultimos_videos"]:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Título": video["title"],
                        "Views": video["views"],
                        "Publicado em": (video["published_at"] or "")[:10],
                    }
                    for video in canal["ultimos_videos"]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum vídeo recente coletado para este canal.")


# --- Tela 4 -----------------------------------------------------------------


def tela_nichos() -> None:
    page_header(
        "⚙️",
        "Configuração de Nichos",
        "Cadastre, edite ou pause nichos sem precisar mexer em código ou pedir ajuda técnica.",
    )

    nichos = carregar(api_client.ranking_de_nichos)
    if nichos is None:
        return

    eyebrow("Situação atual")
    st.subheader("Nichos cadastrados")
    if nichos:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Nicho": nicho["name"],
                        "Keywords": ", ".join(nicho["keywords"] or []),
                        "Situação": "ativo" if nicho["active"] else "pausado",
                        "Canais ativos": nicho["canais_ativos"],
                    }
                    for nicho in nichos
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum nicho cadastrado ainda.")

    st.divider()
    eyebrow("Novo")
    st.subheader("Cadastrar nicho")
    with st.form("novo_nicho"):
        nome = st.text_input("Nome do nicho")
        keywords = st.text_area(
            "Palavras-chave (uma por linha)",
            help="São elas que alimentam a busca de descoberta na API do YouTube.",
        )
        ativo = st.checkbox("Ativo", value=True, help="Nichos inativos não entram no rodízio de descoberta.")
        if st.form_submit_button("➕ Cadastrar nicho", type="primary"):
            resultado = carregar(
                api_client.criar_nicho,
                name=nome,
                keywords=[linha.strip() for linha in keywords.splitlines() if linha.strip()],
                active=ativo,
            )
            if resultado:
                st.success(f"Nicho '{resultado['name']}' cadastrado.")
                st.rerun()

    if not nichos:
        return

    st.divider()
    eyebrow("Ajuste")
    st.subheader("Editar nicho")
    por_nome = {nicho["name"]: nicho for nicho in nichos}
    escolhido = por_nome[st.selectbox("Nicho a editar", list(por_nome.keys()))]
    with st.form("editar_nicho"):
        nome = st.text_input("Nome", value=escolhido["name"])
        keywords = st.text_area(
            "Palavras-chave (uma por linha)", value="\n".join(escolhido["keywords"] or [])
        )
        ativo = st.checkbox(
            "Ativo",
            value=escolhido["active"],
            help="Desmarcar pausa a descoberta do nicho sem apagar o histórico já coletado.",
        )
        if st.form_submit_button("💾 Salvar alterações", type="primary"):
            resultado = carregar(
                api_client.atualizar_nicho,
                escolhido["niche_id"],
                name=nome,
                keywords=[linha.strip() for linha in keywords.splitlines() if linha.strip()],
                active=ativo,
            )
            if resultado:
                st.success(f"Nicho '{resultado['name']}' atualizado.")
                st.rerun()


# --- Tela 5 -----------------------------------------------------------------


def tela_alertas() -> None:
    page_header(
        "🔔",
        "Alertas e Relatórios",
        "Quem já cruzou o limiar de score, e o histórico de avisos disparados por e-mail.",
    )

    config = carregar(api_client.config_de_alertas)
    if config is None:
        return

    limiar_vigente = config["limiar"]
    eyebrow("Configuração vigente")
    colunas = st.columns(2)
    colunas[0].metric("Limiar configurado", limiar_vigente)
    colunas[1].metric("Envio por e-mail", "ativo" if config["email_configurado"] else "não configurado")
    if config["email_configurado"]:
        st.caption(f"Alertas vão para: {', '.join(config['destinatarios'])}")
    else:
        st.warning(
            "SMTP não configurado: os alertas continuam sendo registrados e aparecem "
            "aqui embaixo, mas nenhum e-mail sai."
        )
    st.caption(
        "O limiar vigente vem da variável de ambiente ALERT_SCORE_THRESHOLD. "
        "Use o campo abaixo para simular outro valor antes de alterá-la."
    )

    limiar = st.number_input(
        "Simular limiar",
        min_value=0.0,
        max_value=100.0,
        value=float(limiar_vigente),
        step=5.0,
    )

    dados = carregar(api_client.listar_canais, min_score=limiar, limit=200)
    if dados is None:
        return

    st.divider()
    eyebrow("Simulação")
    st.subheader(f"Canais acima do limiar hoje ({dados['total']})")
    if dados["items"]:
        st.dataframe(
            formatar_canais(dados["items"]).drop(columns=["id", "Link"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum canal cruzou esse limiar até agora.")

    st.divider()
    eyebrow("Registro")
    st.subheader("Histórico de alertas enviados")
    alertas = carregar(api_client.listar_alertas)
    if alertas:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Canal": alerta["channel_name"] or alerta["channel_id"],
                        "Quando": (alerta["triggered_at"] or "")[:19].replace("T", " "),
                        "Motivo": alerta["reason"],
                        "Via": "e-mail" if alerta["channel_out"] == "email" else "só dashboard",
                    }
                    for alerta in alertas
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum alerta disparado até agora.")


# --- navegação --------------------------------------------------------------


def acordar_api_em_segundo_plano() -> None:
    """Começa a acordar a API assim que a landing abre, antes do login.

    Na hospedagem gratuita a API desliga quando fica ociosa e leva dezenas de
    segundos para subir. Se só a chamarmos depois do login, essa espera toda
    acontece com a pessoa olhando para a tela. Disparando aqui, ela acontece
    em paralelo com a leitura da landing e a digitação da senha — quando a
    primeira tela carrega, a API normalmente já está de pé.

    Roda numa thread solta e engole qualquer erro de propósito: isto é só um
    aquecimento, quem trata falha de verdade é o `carregar()` de cada tela.
    """
    if st.session_state.get("api_sendo_acordada"):
        return
    st.session_state["api_sendo_acordada"] = True

    def _aquecer() -> None:
        try:
            api_client.health()
        except Exception:  # noqa: BLE001 - aquecimento não pode derrubar a tela
            pass

    threading.Thread(target=_aquecer, daemon=True).start()


def main() -> None:
    st.set_page_config(page_title="Garimpo de Canais", page_icon="📡", layout="wide")
    # A landing (pré-login) é sempre escura, independente do tema do viewer —
    # ver docs em styles.py. O app autenticado continua seguindo claro/escuro.
    inject_css(landing=not st.session_state.get("autenticado"))
    acordar_api_em_segundo_plano()
    if not autenticar():
        return

    paginas = [
        st.Page(tela_visao_geral, title="Visão Geral", icon="📡", default=True),
        st.Page(tela_canais, title="Canais Descobertos", icon="🔎"),
        st.Page(tela_detalhe, title="Detalhe do Canal", icon="📈"),
        st.Page(tela_nichos, title="Configuração de Nichos", icon="⚙️"),
        st.Page(tela_alertas, title="Alertas e Relatórios", icon="🔔"),
    ]
    # Navegação na barra lateral (posição padrão do st.navigation). A Tela 2
    # soma seus próprios filtros logo abaixo da lista de páginas.
    with st.sidebar:
        st.caption("🌙 Tema: menu ⋮ → Settings", help="Escolha claro ou escuro no menu do topo direito.")
    st.navigation(paginas).run()


# O Streamlit executa este arquivo como "__main__"; o guarda permite importar o
# módulo (nos testes) sem disparar a navegação inteira.
if __name__ == "__main__":
    main()
