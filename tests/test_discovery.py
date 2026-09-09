"""Testes da descoberta compartilhada entre o job agendado e a busca sob
demanda do dashboard (src/scheduler/discovery.py).

Usa o mesmo padrão de serviço falso de tests/test_collectors.py — sem chamada
real à API do YouTube — e o Postgres real para as regras que dependem do
banco (canal já conhecido, sessão suja após cota estourar).
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.collectors.models import ChannelRef
from src.collectors.youtube import YouTubeCollector
from src.db.models import AlertSent, Channel, ChannelScore, ChannelSnapshot, MonetizationSignal, Niche
from src.scheduler.discovery import discover_niche_now, register_candidates

from tests.test_collectors import FakeService, channel_response, quota_error, videos_response

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://garimpo:garimpo123@localhost:5433/garimpo")


@pytest.fixture()
def sessao():
    try:
        engine = create_engine(DATABASE_URL)
        connection = engine.connect()
    except Exception as erro:  # noqa: BLE001
        pytest.skip(f"Postgres indisponível para testes de integração: {erro}")

    transaction = connection.begin()
    sessao = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")()
    for modelo in (AlertSent, ChannelScore, MonetizationSignal, ChannelSnapshot, Channel, Niche):
        sessao.query(modelo).delete()
    sessao.flush()

    yield sessao

    sessao.close()
    transaction.rollback()
    connection.close()


def full_responses():
    return {
        "channels": channel_response(),
        "playlistItems": {
            "items": [
                {"contentDetails": {"videoId": "vid1"}},
                {"contentDetails": {"videoId": "vid2"}},
            ]
        },
        "videos": videos_response(),
        "search": {"items": [{"snippet": {"channelId": "UC123", "channelTitle": "Canal Teste"}}]},
    }


def build_collector(responses, quota_budget=None):
    def factory(api_key):
        return FakeService(responses, api_key)

    return YouTubeCollector(api_keys=["key-1"], quota_budget=quota_budget, service_factory=factory)


def niche(**kwargs):
    dados = {"id": 1, "name": "finanças (teste)", "keywords": ["finanças"]}
    dados.update(kwargs)
    return Niche(**dados)


def test_register_candidates_cadastra_canal_relevante(sessao):
    collector = build_collector(full_responses())
    refs = [ChannelRef(youtube_channel_id="UC123", display_name="Canal Teste")]

    registrados, cota_esgotada = register_candidates(sessao, collector, refs, niche_id=None)

    assert cota_esgotada is False
    assert [c.youtube_channel_id for c in registrados] == ["UC123"]
    assert sessao.query(Channel).filter_by(youtube_channel_id="UC123").first() is not None


def test_register_candidates_ignora_canal_ja_conhecido(sessao):
    sessao.add(Channel(youtube_channel_id="UC123", display_name="Já existe", status="active"))
    sessao.flush()
    collector = build_collector(full_responses())
    refs = [ChannelRef(youtube_channel_id="UC123")]

    registrados, _ = register_candidates(sessao, collector, refs, niche_id=None)

    assert registrados == []


def test_register_candidates_para_de_forma_limpa_quando_a_cota_estoura(sessao):
    """Achado real testando a Fase 2: a exceção não pode simplesmente descartar
    o que já foi encontrado antes de a cota acabar."""
    responses = full_responses()
    responses["channels"] = quota_error()
    collector = build_collector(responses)
    refs = [
        ChannelRef(youtube_channel_id="UC_ja_existe"),
        ChannelRef(youtube_channel_id="UC_nunca_chega"),
    ]
    sessao.add(Channel(youtube_channel_id="UC_ja_existe", status="active"))
    sessao.flush()

    registrados, cota_esgotada = register_candidates(sessao, collector, refs, niche_id=None)

    assert registrados == []
    assert cota_esgotada is True


def test_discover_niche_now_atualiza_last_discovery_at(sessao):
    n = niche()
    sessao.add(n)
    sessao.flush()
    collector = build_collector(full_responses())

    registrados, cota_esgotada = discover_niche_now(sessao, collector, n)

    assert cota_esgotada is False
    assert len(registrados) == 1
    assert registrados[0].niche_id == n.id
    assert n.last_discovery_at is not None


def test_discover_niche_now_preserva_parcial_quando_cota_estoura_no_meio(sessao):
    """O bug corrigido: 4 de 30 candidatos registrados não podem sumir porque
    o 5º estourou a cota — eles já foram gravados e precisam voltar na lista."""
    responses = full_responses()
    n = niche()
    sessao.add(n)
    sessao.flush()

    chamadas = {"n": 0}
    original_fetch_snapshot = YouTubeCollector.fetch_snapshot

    def fetch_snapshot_intermitente(self, ref):
        chamadas["n"] += 1
        if chamadas["n"] > 1:
            from src.collectors.youtube import QuotaExceededError

            raise QuotaExceededError("cota estourada no teste")
        return original_fetch_snapshot(self, ref)

    responses["search"] = {
        "items": [
            {"snippet": {"channelId": "UC123", "channelTitle": "Canal Teste"}},
            {"snippet": {"channelId": "UC_outro", "channelTitle": "Outro"}},
        ]
    }
    collector = build_collector(responses)
    collector.fetch_snapshot = fetch_snapshot_intermitente.__get__(collector, YouTubeCollector)

    registrados, cota_esgotada = discover_niche_now(sessao, collector, n)

    assert cota_esgotada is True
    assert [c.youtube_channel_id for c in registrados] == ["UC123"]
    # O canal já registrado antes de a cota estourar continua na base.
    assert sessao.query(Channel).filter_by(youtube_channel_id="UC123").first() is not None
