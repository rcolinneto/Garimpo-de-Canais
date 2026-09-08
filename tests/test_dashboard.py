"""Testes do dashboard Streamlit.

Usam `streamlit.testing.AppTest`, que executa o script de verdade em modo
headless — é o que prova que as telas renderizam sem exceção. As chamadas de API
são substituídas por respostas fixas, então nenhum teste depende da API no ar.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.config.settings import settings
from src.dashboard import api_client

APP = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")
SENHA = "senha-de-teste"

CANAL = {
    "id": 1,
    "youtube_channel_id": "UC_teste",
    "display_name": "Canal Teste",
    "handle": "@canalteste",
    "url": "https://www.youtube.com/@canalteste",
    "status": "active",
    "discovered_at": "2026-09-01T10:00:00+00:00",
    "niche_id": 1,
    "niche_name": "finanças pessoais",
    "subscriber_count": 1200,
    "total_view_count": 90_000,
    "coletado_em": "2026-09-04T10:00:00+00:00",
    "crescimento_7d": 20.0,
    "crescimento_30d": None,
    "growth_score": 20.0,
    "monetization_score": 50.0,
    "niche_virality_score": 10.0,
    "total_score": 27.0,
    "sinais_monetizacao": ["link_afiliado"],
}

NICHO = {
    "niche_id": 1,
    "name": "finanças pessoais",
    "keywords": ["investimentos"],
    "active": True,
    "canais_ativos": 3,
    "novos_esta_semana": 2,
    "niche_virality_score": 10.0,
    "total_score_medio": 12.0,
    "last_discovery_at": "2026-09-03T18:00:00+00:00",
}

DETALHE = CANAL | {
    "video_count": 40,
    "avg_views_last_n_videos": 3000.0,
    "engagement_rate": 0.04,
    "score_breakdown": {"pesos": {"crescimento": 0.5}},
    "sinais": [
        {
            "signal_type": "link_afiliado",
            "evidence": "https://hotmart.com/curso",
            "confidence": 0.9,
            "detected_at": "2026-09-03T12:00:00+00:00",
        }
    ],
    "ultimos_videos": [
        {"video_id": "v1", "title": "Vídeo recente", "views": 5000, "published_at": "2026-09-02T09:00:00Z"}
    ],
}

HISTORICO = {
    "channel_id": 1,
    "snapshots": [
        {
            "collected_at": "2026-09-01T10:00:00+00:00",
            "subscriber_count": 1000,
            "total_view_count": 80_000,
            "video_count": 38,
            "avg_views_last_n_videos": 2500.0,
            "engagement_rate": 0.03,
        },
        {
            "collected_at": "2026-09-04T10:00:00+00:00",
            "subscriber_count": 1200,
            "total_view_count": 90_000,
            "video_count": 40,
            "avg_views_last_n_videos": 3000.0,
            "engagement_rate": 0.04,
        },
    ],
    "scores": [
        {
            "calculated_at": "2026-09-04T10:00:00+00:00",
            "growth_score": 20.0,
            "monetization_score": 50.0,
            "niche_virality_score": 10.0,
            "total_score": 27.0,
        }
    ],
}


@pytest.fixture(autouse=True)
def api_falsa(monkeypatch):
    """Respostas fixas no lugar da API, para o teste não depender dela no ar."""
    monkeypatch.setattr(settings, "dashboard_password", SENHA)
    monkeypatch.setattr(
        api_client, "listar_canais", lambda **kwargs: {"total": 1, "limit": 50, "offset": 0, "items": [CANAL]}
    )
    monkeypatch.setattr(api_client, "ranking_de_nichos", lambda: [NICHO])
    monkeypatch.setattr(api_client, "detalhar_canal", lambda channel_id: DETALHE)
    monkeypatch.setattr(api_client, "historico_canal", lambda channel_id, days=None: HISTORICO)
    monkeypatch.setattr(
        api_client,
        "historico_do_nicho",
        lambda niche_id, days=90: [{"dia": "2026-09-04T00:00:00+00:00", "niche_virality_score": 10.0}],
    )
    monkeypatch.setattr(
        api_client,
        "config_de_alertas",
        lambda: {"limiar": 50.0, "email_configurado": True, "destinatarios": ["chefe@exemplo.com"]},
    )
    monkeypatch.setattr(
        api_client,
        "listar_alertas",
        lambda limit=100: [
            {
                "id": 1,
                "channel_id": 1,
                "channel_name": "Canal Teste",
                "triggered_at": "2026-09-05T12:00:00+00:00",
                "reason": "score 60.0 cruzou o limiar de 50.0",
                "channel_out": "email",
            }
        ],
    )


def rodar(autenticado: bool = True) -> AppTest:
    """Executa o app inteiro (login + navegação)."""
    app = AppTest.from_file(APP, default_timeout=30)
    if autenticado:
        app.session_state["autenticado"] = True
    return app.run()


def rodar_tela(nome: str) -> AppTest:
    """Executa uma tela isolada, com os globais reais do módulo."""
    app = AppTest.from_string(
        f"from src.dashboard.app import {nome}\n{nome}()", default_timeout=30
    )
    app.session_state["autenticado"] = True
    return app.run()


def test_sem_login_o_dashboard_nao_mostra_dados():
    app = rodar(autenticado=False)

    assert not app.exception
    # A tela de login aparece e nenhuma tabela de canais é renderizada
    assert any("Senha" in entrada.label for entrada in app.text_input)
    assert len(app.dataframe) == 0


def test_landing_explica_o_produto_antes_do_login():
    app = rodar(autenticado=False)

    texto = " ".join(
        [bloco.value for bloco in app.markdown]
        + [bloco.value for bloco in app.caption]
        + [bloco.value for bloco in app.title]
        + [bloco.value for bloco in app.subheader]
    )
    assert "Garimpo de Canais" in texto
    assert "Descobre" in texto and "Detecta monetização" in texto
    # A ressalva de que monetização é estimativa precisa aparecer antes de entrar
    assert any("estima" in aviso.value for aviso in app.info)
    assert any(botao.label == "Entrar" for botao in app.button)


def test_landing_nao_vaza_dados_antes_do_login(monkeypatch):
    """A tela de entrada é pública; os números da empresa não podem estar nela."""
    chamadas = []
    for nome in ("listar_canais", "ranking_de_nichos", "listar_alertas", "config_de_alertas"):
        monkeypatch.setattr(
            api_client, nome, lambda *a, _n=nome, **k: chamadas.append(_n) or {"total": 0, "items": []}
        )

    rodar(autenticado=False)

    assert chamadas == []


def test_senha_errada_nao_autentica():
    app = rodar(autenticado=False)

    app.text_input[0].set_value("senha-errada")
    app.button[0].click().run()

    assert "autenticado" not in app.session_state
    assert any("incorreta" in erro.value.lower() for erro in app.error)


def test_senha_correta_autentica():
    app = rodar(autenticado=False)

    app.text_input[0].set_value(SENHA)
    app.button[0].click().run()

    assert app.session_state["autenticado"] is True


def test_sem_senha_configurada_o_acesso_fica_bloqueado(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "")

    app = rodar(autenticado=False)

    assert any("DASHBOARD_PASSWORD" in erro.value for erro in app.error)
    assert not app.text_input


def test_tela_visao_geral_renderiza():
    app = rodar()

    assert not app.exception
    assert "Visão Geral" in app.title[0].value
    rotulos = [metrica.label for metrica in app.metric]
    assert "Nichos monitorados" in rotulos
    assert "Novos esta semana" in rotulos


@pytest.mark.parametrize(
    "tela",
    ["tela_visao_geral", "tela_canais", "tela_detalhe", "tela_nichos", "tela_alertas"],
)
def test_cada_tela_renderiza_sem_excecao(tela):
    app = rodar_tela(tela)

    assert not app.exception, f"{tela} levantou exceção"


def test_tela_canais_tem_todos_os_filtros_de_docs_06():
    app = rodar_tela("tela_canais")

    rotulos = (
        [entrada.label for entrada in app.selectbox]
        + [entrada.label for entrada in app.number_input]
        + [entrada.label for entrada in app.multiselect]
    )
    assert "Nicho" in rotulos
    assert "Inscritos (mín.)" in rotulos
    assert "Inscritos (máx.)" in rotulos
    assert "Crescimento mín. 7d (%)" in rotulos
    assert "Score mínimo" in rotulos
    assert "Sinais de monetização" in rotulos


def test_tela_canais_oferece_exportacao_csv():
    app = rodar_tela("tela_canais")

    assert any("CSV" in botao.label for botao in app.get("download_button"))


def test_tela_detalhe_mostra_evidencia_do_sinal():
    app = rodar_tela("tela_detalhe")

    tabelas = [tabela.value for tabela in app.dataframe]
    evidencias = [
        tabela["Evidência"].tolist() for tabela in tabelas if "Evidência" in getattr(tabela, "columns", [])
    ]
    assert ["https://hotmart.com/curso"] in evidencias


def test_tela_alertas_mostra_limiar_e_historico():
    app = rodar_tela("tela_alertas")

    rotulos = [metrica.label for metrica in app.metric]
    assert "Limiar configurado" in rotulos
    assert "Envio por e-mail" in rotulos
    tabelas = [tabela.value for tabela in app.dataframe]
    motivos = [
        tabela["Motivo"].tolist() for tabela in tabelas if "Motivo" in getattr(tabela, "columns", [])
    ]
    assert ["score 60.0 cruzou o limiar de 50.0"] in motivos


def test_tela_alertas_avisa_quando_smtp_nao_esta_configurado(monkeypatch):
    monkeypatch.setattr(
        api_client,
        "config_de_alertas",
        lambda: {"limiar": 50.0, "email_configurado": False, "destinatarios": []},
    )

    app = rodar_tela("tela_alertas")

    assert any("SMTP não configurado" in aviso.value for aviso in app.warning)


def test_tela_nichos_usa_a_api_para_criar(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        api_client,
        "criar_nicho",
        lambda name, keywords, active: chamadas.append((name, keywords, active)) or NICHO,
    )

    app = rodar_tela("tela_nichos")
    app.text_input[0].set_value("culinária fitness")
    app.text_area[0].set_value("marmita fit\nlow carb")
    app.button[0].click().run()

    # O CRUD passa pela API, nunca pelo banco (regra de docs/02-arquitetura.md)
    assert chamadas == [("culinária fitness", ["marmita fit", "low carb"], True)]
