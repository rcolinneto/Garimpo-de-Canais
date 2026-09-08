"""Testes dos endpoints da API.

Rodam contra o Postgres real porque as consultas usam recursos específicos dele
(DISTINCT ON, joins laterais, JSONB) — em SQLite não seriam o mesmo código. Cada
teste roda dentro de uma transação revertida no fim, então nada é gravado de fato.
Se o banco não estiver de pé, os testes são pulados em vez de falharem.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app, get_session
from src.db.models import (
    AlertSent,
    Channel,
    ChannelScore,
    ChannelSnapshot,
    MonetizationSignal,
    Niche,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://garimpo:garimpo123@localhost:5433/garimpo")

AGORA = datetime.now(timezone.utc)


def _limpar(session) -> None:
    """Esvazia as tabelas para os testes partirem de uma base determinística.

    Seguro porque tudo roda dentro de uma transação que é revertida no fim do
    teste — os dados reais coletados continuam intactos no banco.
    """
    for modelo in (AlertSent, ChannelScore, MonetizationSignal, ChannelSnapshot, Channel, Niche):
        session.query(modelo).delete()
    session.flush()


def _seed(session) -> dict:
    _limpar(session)
    nicho_financas = Niche(name="finanças (teste)", keywords=["finanças", "investimentos"], active=True)
    nicho_pets = Niche(name="pets (teste)", keywords=["pets exóticos"], active=True)
    session.add_all([nicho_financas, nicho_pets])
    session.flush()

    canal_top = Channel(
        youtube_channel_id="UC_teste_top",
        display_name="Canal Top",
        handle="@canaltop",
        url="https://www.youtube.com/@canaltop",
        niche_id=nicho_financas.id,
        discovered_at=AGORA - timedelta(days=3),
        first_seen_subscriber_count=10_000,
        status="active",
    )
    canal_pequeno = Channel(
        youtube_channel_id="UC_teste_pequeno",
        display_name="Canal Pequeno",
        niche_id=nicho_pets.id,
        discovered_at=AGORA - timedelta(days=40),
        status="active",
    )
    canal_removido = Channel(
        youtube_channel_id="UC_teste_removido",
        display_name="Canal Removido",
        niche_id=nicho_financas.id,
        discovered_at=AGORA - timedelta(days=20),
        status="removed",
    )
    session.add_all([canal_top, canal_pequeno, canal_removido])
    session.flush()

    session.add_all(
        [
            ChannelSnapshot(
                channel_id=canal_top.id,
                collected_at=AGORA - timedelta(days=8),
                subscriber_count=10_000,
                total_view_count=500_000,
                video_count=50,
            ),
            ChannelSnapshot(
                channel_id=canal_top.id,
                collected_at=AGORA,
                subscriber_count=12_000,
                total_view_count=650_000,
                video_count=55,
                avg_views_last_n_videos=8_000,
                engagement_rate=0.05,
                raw_payload={
                    "recent_videos": [
                        {
                            "id": "vid1",
                            "snippet": {"title": "Vídeo recente", "publishedAt": "2026-09-01T10:00:00Z"},
                            "statistics": {"viewCount": "9000"},
                        }
                    ]
                },
            ),
            ChannelSnapshot(
                channel_id=canal_pequeno.id,
                collected_at=AGORA,
                subscriber_count=500,
                total_view_count=20_000,
                video_count=10,
            ),
            ChannelSnapshot(
                channel_id=canal_removido.id,
                collected_at=AGORA - timedelta(days=5),
                subscriber_count=1_000,
            ),
        ]
    )

    session.add_all(
        [
            ChannelScore(
                channel_id=canal_top.id,
                calculated_at=AGORA,
                growth_score=20.0,
                monetization_score=50.0,
                niche_virality_score=20.0,
                total_score=29.0,
                score_breakdown={"pesos": {"crescimento": 0.5}},
            ),
            ChannelScore(
                channel_id=canal_pequeno.id,
                calculated_at=AGORA,
                growth_score=0.0,
                monetization_score=0.0,
                niche_virality_score=0.0,
                total_score=0.0,
                score_breakdown={},
            ),
        ]
    )

    session.add(
        AlertSent(
            channel_id=canal_top.id,
            triggered_at=AGORA - timedelta(hours=2),
            reason="score 29.0 cruzou o limiar de 25.0",
            channel_out="email",
        )
    )
    session.add(
        MonetizationSignal(
            channel_id=canal_top.id,
            detected_at=AGORA - timedelta(days=1),
            signal_type="link_afiliado",
            evidence="https://hotmart.com/curso-teste",
            confidence=0.9,
        )
    )
    session.flush()

    return {
        "canal_top": canal_top.id,
        "canal_pequeno": canal_pequeno.id,
        "canal_removido": canal_removido.id,
        "nicho_financas": nicho_financas.id,
        "nicho_pets": nicho_pets.id,
    }


@pytest.fixture()
def api():
    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"Postgres indisponível para testes de integração: {error}")

    transaction = connection.begin()
    # create_savepoint: os endpoints de escrita chamam commit(), e sem isso o
    # commit deles encerraria a transação externa, furando o rollback do teste.
    session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")()
    ids = _seed(session)
    app.dependency_overrides[get_session] = lambda: session

    yield TestClient(app), ids

    app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()


def test_health(api):
    client, _ = api

    resposta = client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_listagem_traz_so_ativos_ordenados_por_score(api):
    client, ids = api

    dados = client.get("/canais").json()

    nomes = [item["display_name"] for item in dados["items"]]
    assert "Canal Removido" not in nomes
    # Ordenação padrão: total_score decrescente
    assert nomes.index("Canal Top") < nomes.index("Canal Pequeno")


def test_listagem_calcula_crescimento_e_badges(api):
    client, ids = api

    dados = client.get("/canais").json()
    canal = next(item for item in dados["items"] if item["id"] == ids["canal_top"])

    # 10.000 -> 12.000 inscritos = +20%
    assert canal["crescimento_7d"] == pytest.approx(20.0)
    # Não há snapshot com mais de 30 dias, então não há base de comparação
    assert canal["crescimento_30d"] is None
    assert canal["sinais_monetizacao"] == ["link_afiliado"]
    assert canal["niche_name"] == "finanças (teste)"


def test_filtros_da_tela_2(api):
    client, ids = api

    por_nicho = client.get("/canais", params={"niche_id": ids["nicho_pets"]}).json()
    por_score = client.get("/canais", params={"min_score": 10}).json()
    por_inscritos = client.get("/canais", params={"min_subscribers": 1000}).json()
    por_sinal = client.get("/canais", params={"signal_types": ["link_afiliado"]}).json()
    por_crescimento = client.get("/canais", params={"min_growth": 50}).json()

    assert [item["display_name"] for item in por_nicho["items"]] == ["Canal Pequeno"]
    assert [item["display_name"] for item in por_score["items"]] == ["Canal Top"]
    assert [item["display_name"] for item in por_inscritos["items"]] == ["Canal Top"]
    assert [item["display_name"] for item in por_sinal["items"]] == ["Canal Top"]
    # Nenhum canal cresceu 50% em 7 dias
    assert por_crescimento["items"] == []


def test_filtro_de_canais_novos_dos_ultimos_dias(api):
    """Critério de sucesso de docs/01: ver o que surgiu nos últimos X dias."""
    client, _ = api

    recentes = client.get("/canais", params={"discovered_since_days": 7}).json()
    antigos = client.get("/canais", params={"discovered_since_days": 90}).json()

    # Canal Top foi descoberto há 3 dias; Canal Pequeno, há 40
    assert [item["display_name"] for item in recentes["items"]] == ["Canal Top"]
    assert len(antigos["items"]) == 2


def test_paginacao_reporta_total(api):
    client, _ = api

    dados = client.get("/canais", params={"limit": 1}).json()

    assert dados["total"] == 2
    assert len(dados["items"]) == 1
    assert dados["limit"] == 1


def test_detalhe_traz_evidencias_e_ultimos_videos(api):
    client, ids = api

    dados = client.get(f"/canais/{ids['canal_top']}").json()

    assert dados["display_name"] == "Canal Top"
    assert dados["sinais"][0]["signal_type"] == "link_afiliado"
    # A evidência é o que o chefe abre para conferir manualmente
    assert dados["sinais"][0]["evidence"] == "https://hotmart.com/curso-teste"
    assert dados["ultimos_videos"][0]["views"] == 9000
    assert dados["score_breakdown"] == {"pesos": {"crescimento": 0.5}}


def test_detalhe_de_canal_inexistente_da_404(api):
    client, _ = api

    assert client.get("/canais/999999").status_code == 404


def test_historico_devolve_as_duas_series(api):
    client, ids = api

    dados = client.get(f"/canais/{ids['canal_top']}/historico").json()

    assert len(dados["snapshots"]) == 2
    # Ordem cronológica, para o gráfico não sair invertido
    assert dados["snapshots"][0]["subscriber_count"] == 10_000
    assert dados["snapshots"][1]["subscriber_count"] == 12_000
    assert len(dados["scores"]) == 1


def test_historico_respeita_janela_de_dias(api):
    client, ids = api

    dados = client.get(f"/canais/{ids['canal_top']}/historico", params={"days": 2}).json()

    assert len(dados["snapshots"]) == 1


def test_ranking_de_nichos(api):
    client, ids = api

    dados = client.get("/nichos/ranking").json()
    por_id = {item["niche_id"]: item for item in dados}

    financas = por_id[ids["nicho_financas"]]
    # O canal removido não conta como ativo
    assert financas["canais_ativos"] == 1
    assert financas["novos_esta_semana"] == 1
    assert financas["niche_virality_score"] == pytest.approx(20.0)
    # Nicho com score maior vem primeiro
    assert dados[0]["niche_id"] == ids["nicho_financas"]


def test_historico_do_nicho(api):
    client, ids = api

    dados = client.get(f"/nichos/{ids['nicho_financas']}/historico").json()

    assert len(dados) == 1
    assert dados[0]["niche_virality_score"] == pytest.approx(20.0)


def test_historico_de_nicho_inexistente_da_404(api):
    client, _ = api

    assert client.get("/nichos/999999/historico").status_code == 404


def test_lista_alertas_enviados(api):
    client, ids = api

    dados = client.get("/alertas").json()

    assert len(dados) == 1
    assert dados[0]["channel_name"] == "Canal Top"
    assert dados[0]["channel_out"] == "email"
    assert "cruzou o limiar" in dados[0]["reason"]


def test_config_de_alertas_informa_limiar_e_situacao_do_email(api):
    client, _ = api

    config = client.get("/alertas/config").json()

    assert isinstance(config["limiar"], (int, float))
    assert isinstance(config["email_configurado"], bool)
    assert isinstance(config["destinatarios"], list)


def test_cria_nicho(api):
    client, _ = api

    resposta = client.post(
        "/nichos", json={"name": "  culinária fitness  ", "keywords": ["marmita fit", " low carb "]}
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    # Nome e keywords chegam normalizados, sem espaços sobrando
    assert corpo["name"] == "culinária fitness"
    assert corpo["keywords"] == ["marmita fit", "low carb"]
    assert corpo["active"] is True
    # O nicho novo aparece na listagem consumida pela Tela 4
    nomes = [item["name"] for item in client.get("/nichos/ranking").json()]
    assert "culinária fitness" in nomes


def test_cria_nicho_com_payload_invalido(api):
    client, _ = api

    sem_nome = client.post("/nichos", json={"keywords": ["algo"]})
    nome_vazio = client.post("/nichos", json={"name": ""})
    tipo_errado = client.post("/nichos", json={"name": "x", "keywords": "não é lista"})

    assert sem_nome.status_code == 422
    assert nome_vazio.status_code == 422
    assert tipo_errado.status_code == 422


def test_nao_permite_dois_nichos_com_o_mesmo_nome(api):
    client, _ = api

    duplicado = client.post("/nichos", json={"name": "FINANÇAS (TESTE)"})

    assert duplicado.status_code == 409


def test_edita_nicho(api):
    client, ids = api

    resposta = client.put(
        f"/nichos/{ids['nicho_pets']}",
        json={"name": "pets exóticos revisado", "keywords": ["répteis"]},
    )

    assert resposta.status_code == 200
    assert resposta.json()["name"] == "pets exóticos revisado"
    assert resposta.json()["keywords"] == ["répteis"]
    # Edição parcial não mexe no que não foi enviado
    assert resposta.json()["active"] is True


def test_pausar_nicho_preserva_o_historico(api):
    client, ids = api

    resposta = client.put(f"/nichos/{ids['nicho_financas']}", json={"active": False})

    assert resposta.status_code == 200
    assert resposta.json()["active"] is False
    # Pausar não apaga: o nicho e seus canais continuam consultáveis
    ranking = {item["niche_id"]: item for item in client.get("/nichos/ranking").json()}
    assert ranking[ids["nicho_financas"]]["canais_ativos"] == 1


def test_edita_nicho_inexistente_da_404(api):
    client, _ = api

    assert client.put("/nichos/999999", json={"active": False}).status_code == 404


def test_edicao_com_payload_invalido(api):
    client, ids = api

    resposta = client.put(f"/nichos/{ids['nicho_pets']}", json={"active": "talvez"})

    assert resposta.status_code == 422
