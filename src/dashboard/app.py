"""Dashboard do Garimpo de Canais (docs/06-dashboard.md).

Consome exclusivamente a API interna — nenhuma consulta ao banco sai daqui,
conforme `docs/02-arquitetura.md`.

Execução: streamlit run src/dashboard/app.py
"""

import hmac

import pandas as pd
import streamlit as st

from src.config.settings import settings
from src.dashboard import api_client
from src.dashboard.api_client import ApiError

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


# --- autenticação -----------------------------------------------------------


def autenticar() -> bool:
    """Senha compartilhada via variável de ambiente (docs/06, seção Autenticação)."""
    if st.session_state.get("autenticado"):
        return True

    st.title("Garimpo de Canais")
    if not settings.dashboard_password:
        # Falha fechada: o dashboard expõe análise de mercado da empresa, então
        # ficar aberto por falta de configuração seria pior que não subir.
        st.error(
            "DASHBOARD_PASSWORD não configurada. Defina a variável de ambiente "
            "para liberar o acesso ao dashboard."
        )
        return False

    with st.form("login"):
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if hmac.compare_digest(senha, settings.dashboard_password):
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False


# --- helpers ----------------------------------------------------------------


def carregar(funcao, *args, **kwargs):
    """Executa uma chamada de API mostrando o erro na tela em vez de estourar."""
    try:
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
                "Inscritos": item["subscriber_count"],
                "Cresc. 7d (%)": _arredondar(item["crescimento_7d"]),
                "Cresc. 30d (%)": _arredondar(item["crescimento_30d"]),
                "Sinais": ", ".join(item["sinais_monetizacao"]) or "—",
                "Score": _arredondar(item["total_score"]),
                "Descoberto em": (item["discovered_at"] or "")[:10],
                "id": item["id"],
            }
            for item in itens
        ]
    )


def _arredondar(valor, casas: int = 2):
    return round(valor, casas) if isinstance(valor, (int, float)) else None


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
    st.title("Visão Geral — Radar de Nichos")
    st.caption("O que está bombando agora, por nicho monitorado.")

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

    st.subheader("Nichos por viralidade")
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
    st.line_chart(serie.set_index("dia")["niche_virality_score"])


# --- Tela 2 -----------------------------------------------------------------


def tela_canais() -> None:
    st.title("Canais Descobertos")

    nichos = carregar(api_client.ranking_de_nichos) or []
    opcoes_nicho = {"Todos": None} | {nicho["name"]: nicho["niche_id"] for nicho in nichos}

    with st.sidebar:
        st.header("Filtros")
        nicho = st.selectbox("Nicho", list(opcoes_nicho.keys()))
        min_subs, max_subs = st.columns(2)
        minimo_inscritos = min_subs.number_input("Inscritos (mín.)", min_value=0, value=0, step=100)
        maximo_inscritos = max_subs.number_input("Inscritos (máx.)", min_value=0, value=0, step=1000)
        crescimento = st.number_input("Crescimento mín. 7d (%)", value=0.0, step=1.0)
        score_minimo = st.number_input("Score mínimo", min_value=0.0, value=0.0, step=1.0)
        sinais = st.multiselect("Sinais de monetização", TIPOS_DE_SINAL)
        limite = st.slider("Máximo de canais", min_value=10, max_value=200, value=50, step=10)

    dados = carregar(
        api_client.listar_canais,
        niche_id=opcoes_nicho[nicho],
        min_subscribers=minimo_inscritos or None,
        max_subscribers=maximo_inscritos or None,
        min_growth=crescimento or None,
        min_score=score_minimo or None,
        signal_types=sinais or None,
        limit=limite,
    )
    if dados is None:
        return

    itens = dados["items"]
    st.caption(f"{len(itens)} de {dados['total']} canais no filtro atual, ordenados por score.")
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
        "Exportar CSV da visão atual",
        data=tabela.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
        file_name="canais_garimpados.csv",
        mime="text/csv",
    )

    st.subheader("Abrir detalhe")
    escolhido = selecionar_canal(itens, "canal_tela2")
    if st.button("Selecionar canal"):
        st.session_state["canal_selecionado"] = escolhido
        st.success("Canal selecionado — abra a página 'Detalhe do Canal' no menu ao lado.")


# --- Tela 3 -----------------------------------------------------------------


def tela_detalhe() -> None:
    st.title("Detalhe do Canal")

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
    colunas = st.columns(4)
    colunas[0].metric("Inscritos", canal["subscriber_count"] or "oculto")
    colunas[1].metric("Score total", _arredondar(canal["total_score"]))
    colunas[2].metric("Nicho", canal["niche_name"] or "—")
    colunas[3].metric("Descoberto em", (canal["discovered_at"] or "")[:10])
    if canal["url"]:
        st.markdown(f"[Abrir canal no YouTube]({canal['url']})")

    historico = carregar(api_client.historico_canal, channel_id)
    if historico:
        snapshots = pd.DataFrame(historico["snapshots"])
        if not snapshots.empty:
            snapshots["collected_at"] = pd.to_datetime(snapshots["collected_at"])
            snapshots = snapshots.set_index("collected_at")
            # Dois gráficos em vez de um: inscritos e views têm escalas muito
            # diferentes, e juntos achatariam a linha de inscritos.
            st.subheader("Evolução de inscritos")
            st.line_chart(snapshots["subscriber_count"])
            st.subheader("Evolução de views totais")
            st.line_chart(snapshots["total_view_count"])

        scores = pd.DataFrame(historico["scores"])
        if not scores.empty:
            scores["calculated_at"] = pd.to_datetime(scores["calculated_at"])
            st.subheader("Evolução do score e seus componentes")
            st.line_chart(
                scores.set_index("calculated_at")[
                    ["total_score", "growth_score", "monetization_score", "niche_virality_score"]
                ]
            )

    st.subheader("Sinais de monetização detectados")
    if canal["sinais"]:
        st.caption("A evidência é o que motivou cada detecção — confira antes de agir sobre ela.")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Tipo": sinal["signal_type"],
                        "Confiança": sinal["confidence"],
                        "Evidência": sinal["evidence"],
                        "Detectado em": (sinal["detected_at"] or "")[:10],
                    }
                    for sinal in canal["sinais"]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum sinal de monetização detectado para este canal até agora.")

    if canal["score_breakdown"]:
        with st.expander("Por que este canal tem esse score?"):
            st.json(canal["score_breakdown"])

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
    st.title("Configuração de Nichos")
    st.caption("Cadastre, edite ou pause nichos sem precisar mexer em código.")

    nichos = carregar(api_client.ranking_de_nichos)
    if nichos is None:
        return

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

    st.subheader("Cadastrar nicho")
    with st.form("novo_nicho"):
        nome = st.text_input("Nome do nicho")
        keywords = st.text_area(
            "Palavras-chave (uma por linha)",
            help="São elas que alimentam a busca de descoberta na API do YouTube.",
        )
        ativo = st.checkbox("Ativo", value=True)
        if st.form_submit_button("Cadastrar"):
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
        if st.form_submit_button("Salvar alterações"):
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
    st.title("Alertas e Relatórios")

    config = carregar(api_client.config_de_alertas)
    if config is None:
        return

    limiar_vigente = config["limiar"]
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

    st.subheader(f"Canais acima do limiar hoje ({dados['total']})")
    if dados["items"]:
        st.dataframe(
            formatar_canais(dados["items"]).drop(columns=["id", "Link"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("Nenhum canal cruzou esse limiar até agora.")

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
        st.write("Nenhum alerta disparado até agora.")


# --- navegação --------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title="Garimpo de Canais", page_icon="📡", layout="wide")
    if not autenticar():
        return

    paginas = [
        st.Page(tela_visao_geral, title="Visão Geral", icon="📡", default=True),
        st.Page(tela_canais, title="Canais Descobertos", icon="🔎"),
        st.Page(tela_detalhe, title="Detalhe do Canal", icon="📈"),
        st.Page(tela_nichos, title="Configuração de Nichos", icon="⚙️"),
        st.Page(tela_alertas, title="Alertas e Relatórios", icon="🔔"),
    ]
    st.navigation(paginas).run()


# O Streamlit executa este arquivo como "__main__"; o guarda permite importar o
# módulo (nos testes) sem disparar a navegação inteira.
if __name__ == "__main__":
    main()
