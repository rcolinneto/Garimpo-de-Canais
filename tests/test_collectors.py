import json

import pytest
from googleapiclient.errors import HttpError

from src.collectors.models import ChannelRef, ChannelSnapshot
from src.collectors.youtube import (
    CHANNELS_LIST_COST,
    PLAYLIST_ITEMS_LIST_COST,
    SEARCH_LIST_COST,
    VIDEOS_LIST_COST,
    QuotaExceededError,
    YouTubeCollector,
    is_relevant_candidate,
)


class FakeRequest:
    def __init__(self, response, error=None):
        self._response = response
        self._error = error

    def execute(self):
        if self._error:
            raise self._error
        return self._response


class FakeResource:
    """Reproduz o encadeamento `service.channels().list(...).execute()`."""

    def __init__(self, service, name):
        self._service = service
        self._name = name

    def list(self, **params):
        self._service.calls.append((self._name, params))
        response = self._service.responses.get(self._name, {})
        if isinstance(response, Exception):
            return FakeRequest(None, error=response)
        return FakeRequest(response)


class FakeService:
    def __init__(self, responses=None, api_key="key"):
        self.responses = responses or {}
        self.calls = []
        self.api_key = api_key

    def channels(self):
        return FakeResource(self, "channels")

    def videos(self):
        return FakeResource(self, "videos")

    def playlistItems(self):
        return FakeResource(self, "playlistItems")

    def search(self):
        return FakeResource(self, "search")


def quota_error():
    content = json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}]}}).encode()
    resp = type("Resp", (), {"status": 403, "reason": "Forbidden"})()
    return HttpError(resp, content)


def channel_response(statistics=None, uploads="UUxyz"):
    return {
        "items": [
            {
                "id": "UC123",
                "snippet": {
                    "title": "Canal Teste",
                    "description": "Meu curso: https://hotmart.com/curso",
                    "customUrl": "@canalteste",
                    "publishedAt": "2025-01-05T10:00:00Z",
                },
                "statistics": statistics
                if statistics is not None
                else {"subscriberCount": "1000", "viewCount": "50000", "videoCount": "20"},
                "contentDetails": {"relatedPlaylists": {"uploads": uploads}},
            }
        ]
    }


def videos_response():
    return {
        "items": [
            {
                "id": "vid1",
                "snippet": {
                    "title": "Vídeo 1",
                    "description": "Link de afiliado https://amzn.to/abc",
                    "publishedAt": "2026-08-01T10:00:00Z",
                },
                "statistics": {"viewCount": "1000", "likeCount": "80", "commentCount": "20"},
            },
            {
                "id": "vid2",
                "snippet": {"title": "Vídeo 2", "description": "", "publishedAt": "2026-08-10T10:00:00Z"},
                "statistics": {"viewCount": "3000", "likeCount": "100", "commentCount": "0"},
            },
        ]
    }


def build_collector(responses, api_keys=None, quota_budget=None):
    services = []

    def factory(api_key):
        service = FakeService(responses, api_key)
        services.append(service)
        return service

    collector = YouTubeCollector(
        api_keys=api_keys or ["key-1"], quota_budget=quota_budget, service_factory=factory
    )
    return collector, services


def full_responses():
    return {
        "channels": channel_response(),
        "playlistItems": {"items": [{"contentDetails": {"videoId": "vid1"}}, {"contentDetails": {"videoId": "vid2"}}]},
        "videos": videos_response(),
    }


def test_fetch_snapshot_agrega_metricas_e_custa_tres_unidades():
    collector, _ = build_collector(full_responses())

    snapshot = collector.fetch_snapshot(ChannelRef(youtube_channel_id="UC123"))

    assert snapshot is not None
    assert snapshot.subscriber_count == 1000
    assert snapshot.total_view_count == 50000
    assert snapshot.video_count == 20
    # (1000 + 3000) / 2
    assert snapshot.avg_views_last_n_videos == 2000
    # (80 + 20 + 100 + 0) / 4000
    assert snapshot.engagement_rate == pytest.approx(0.05)
    assert snapshot.max_recent_video_views == 3000
    assert collector.units_consumed == CHANNELS_LIST_COST + PLAYLIST_ITEMS_LIST_COST + VIDEOS_LIST_COST


def test_canal_removido_devolve_none():
    collector, _ = build_collector({"channels": {"items": []}})

    assert collector.fetch_snapshot(ChannelRef(youtube_channel_id="UC123")) is None


def test_inscritos_ocultos_viram_none_e_nao_zero():
    responses = full_responses()
    responses["channels"] = channel_response(
        statistics={"hiddenSubscriberCount": True, "subscriberCount": "0", "viewCount": "900", "videoCount": "3"}
    )
    collector, _ = build_collector(responses)

    snapshot = collector.fetch_snapshot(ChannelRef(youtube_channel_id="UC123"))

    assert snapshot is not None
    assert snapshot.subscriber_count is None


def test_content_signals_reaproveitam_o_snapshot_sem_gastar_cota_extra():
    collector, _ = build_collector(full_responses())
    ref = ChannelRef(youtube_channel_id="UC123")

    collector.fetch_snapshot(ref)
    units_after_snapshot = collector.units_consumed
    signals = collector.fetch_recent_content_signals(ref)

    assert collector.units_consumed == units_after_snapshot
    sources = [signal.source for signal in signals]
    assert "channel_description" in sources
    assert sources.count("video_description") == 1  # o vídeo 2 tem descrição vazia
    assert any("hotmart.com" in signal.text for signal in signals)


def test_discovery_usa_uma_unica_busca_por_nicho():
    responses = full_responses()
    responses["search"] = {
        "items": [
            {"snippet": {"channelId": "UC1", "channelTitle": "A"}},
            {"snippet": {"channelId": "UC1", "channelTitle": "A"}},
            {"snippet": {"channelId": "UC2", "channelTitle": "B"}},
        ]
    }
    collector, services = build_collector(responses)

    refs = collector.discover_candidates(["finanças pessoais", "investimentos"])

    search_calls = [call for call in services[0].calls if call[0] == "search"]
    assert len(search_calls) == 1
    # keywords combinadas com OR para não pagar 100 unidades por keyword
    assert search_calls[0][1]["q"] == "finanças pessoais|investimentos"
    assert collector.units_consumed == SEARCH_LIST_COST
    assert [ref.youtube_channel_id for ref in refs] == ["UC1", "UC2"]


def test_orcamento_de_cota_interrompe_antes_de_estourar():
    collector, _ = build_collector(full_responses(), quota_budget=SEARCH_LIST_COST - 1)

    with pytest.raises(QuotaExceededError):
        collector.discover_candidates(["qualquer coisa"])

    assert collector.units_consumed == 0


def test_rotaciona_para_a_proxima_chave_quando_a_cota_estoura():
    responses = full_responses()
    used_keys = []

    # A primeira chave responde com quotaExceeded; a segunda funciona.
    def factory(api_key):
        used_keys.append(api_key)
        if api_key == "key-1":
            return FakeService({"channels": quota_error()}, api_key)
        return FakeService(responses, api_key)

    collector = YouTubeCollector(api_keys=["key-1", "key-2"], service_factory=factory)
    snapshot = collector.fetch_snapshot(ChannelRef(youtube_channel_id="UC123"))

    assert snapshot is not None
    assert snapshot.subscriber_count == 1000
    assert used_keys == ["key-1", "key-2"]


def test_cota_estourada_em_todas_as_chaves_vira_quota_exceeded():
    collector, _ = build_collector({"channels": quota_error()}, api_keys=["key-1"])

    with pytest.raises(QuotaExceededError):
        collector.fetch_snapshot(ChannelRef(youtube_channel_id="UC123"))


def snapshot_with(subscribers, max_views, display_name="Canal Teste"):
    return ChannelSnapshot(
        channel_ref=ChannelRef(youtube_channel_id="UC123", display_name=display_name),
        collected_at="2026-09-03T10:00:00Z",
        subscriber_count=subscribers,
        max_recent_video_views=max_views,
    )


@pytest.mark.parametrize(
    "subscribers,max_views,esperado",
    [
        (5_000, 20_000, True),  # canal pequeno com vídeo estourando
        (5_000, 1_000, False),  # views abaixo do tamanho do canal
        (5_000_000, 9_000_000, False),  # canal grande demais para "descoberta"
        (None, 10_000, True),  # inscritos ocultos, mas tem vídeo recente
        (5_000, None, False),  # sem vídeo recente com views
    ],
)
def test_filtro_de_relevancia(subscribers, max_views, esperado):
    snapshot = snapshot_with(subscribers, max_views)

    assert is_relevant_candidate(snapshot, max_subscribers=100_000, min_view_subscriber_ratio=1.0) is esperado


def test_filtro_descarta_canais_topic_gerados_pelo_youtube():
    snapshot = snapshot_with(5_000, 20_000, display_name="Nicolle Kaduta - Topic")

    assert is_relevant_candidate(snapshot, max_subscribers=100_000, min_view_subscriber_ratio=1.0) is False
