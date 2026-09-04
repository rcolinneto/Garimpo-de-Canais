"""Coleta na YouTube Data API v3.

Estratégia de cota (docs/04-coleta-youtube.md): a chave tem 10.000 unidades/dia.
`search.list` custa 100 unidades e por isso só aparece na descoberta; `channels.list`,
`videos.list` e `playlistItems.list` custam 1 unidade cada e sustentam todo o resto
(snapshots diários, vídeos recentes, textos para o motor de monetização).
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.collectors.models import ChannelRef, ChannelSnapshot, ContentSignal
from src.config.settings import settings

logger = logging.getLogger(__name__)

SEARCH_LIST_COST = 100
CHANNELS_LIST_COST = 1
VIDEOS_LIST_COST = 1
PLAYLIST_ITEMS_LIST_COST = 1

# Motivos de erro da API que significam "acabou a cota", e não uma falha pontual.
_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}


class QuotaExceededError(RuntimeError):
    """Cota esgotada: o job deve parar de forma limpa e retomar na próxima execução."""


def _default_service_factory(api_key: str) -> Any:
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def _is_quota_error(error: HttpError) -> bool:
    if error.resp.status != 403:
        return False
    try:
        payload = json.loads(error.content.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, ValueError):
        return "quota" in str(error).lower()
    reasons = {item.get("reason") for item in payload.get("error", {}).get("errors", [])}
    return bool(reasons & _QUOTA_REASONS)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_published_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _channel_url(channel_id: str, custom_url: str | None) -> str:
    if custom_url:
        handle = custom_url if custom_url.startswith("@") else f"@{custom_url}"
        return f"https://www.youtube.com/{handle}"
    return f"https://www.youtube.com/channel/{channel_id}"


def _ref_from_channel_item(item: dict) -> ChannelRef:
    channel_id = item.get("id", "")
    snippet = item.get("snippet", {})
    custom_url = snippet.get("customUrl")
    return ChannelRef(
        youtube_channel_id=channel_id,
        handle=custom_url,
        display_name=snippet.get("title"),
        url=_channel_url(channel_id, custom_url),
    )


def _aggregate_video_stats(videos: list[dict]) -> tuple[float | None, float | None, int | None]:
    """Média de views, taxa de engajamento e maior view entre os vídeos recentes.

    engagement_rate = (curtidas + comentários) / views das últimas N publicações.
    """
    views: list[int] = []
    interactions = 0
    for video in videos:
        stats = video.get("statistics", {})
        view_count = _to_int(stats.get("viewCount"))
        if view_count is None:
            # Vídeo pode ocultar estatísticas — ignorar em vez de contar como zero.
            continue
        views.append(view_count)
        interactions += (_to_int(stats.get("likeCount")) or 0) + (
            _to_int(stats.get("commentCount")) or 0
        )
    if not views:
        return None, None, None
    total_views = sum(views)
    avg_views = total_views / len(views)
    engagement_rate = interactions / total_views if total_views else None
    return avg_views, engagement_rate, max(views)


def _is_auto_generated_topic_channel(display_name: str | None) -> bool:
    """Canais "- Topic" são gerados automaticamente pelo YouTube para artistas.

    Não têm criador por trás para monetizar nem descrição para analisar, então só
    poluiriam a base — aparecem bastante na descoberta por vídeos em alta.
    """
    return bool(display_name) and display_name.strip().endswith("- Topic")


def is_relevant_candidate(
    snapshot: ChannelSnapshot,
    max_subscribers: int | None = None,
    min_view_subscriber_ratio: float | None = None,
) -> bool:
    """Filtro mínimo de relevância da descoberta (docs/04-coleta-youtube.md).

    Só entra na base o canal que ainda é pequeno E tem pelo menos um vídeo recente
    com views desproporcionais ao seu tamanho (sinal de crescimento inicial).
    """
    max_subs = max_subscribers if max_subscribers is not None else settings.discovery_max_subscribers
    ratio = (
        min_view_subscriber_ratio
        if min_view_subscriber_ratio is not None
        else settings.discovery_min_view_subscriber_ratio
    )

    if _is_auto_generated_topic_channel(snapshot.channel_ref.display_name):
        return False
    if snapshot.max_recent_video_views is None:
        return False
    subscribers = snapshot.subscriber_count
    if subscribers is not None and subscribers > max_subs:
        return False
    if not subscribers:
        # Inscritos ocultos ou zerados: não dá para medir proporção, mas o canal já
        # passou pela exigência de ter vídeo recente com views.
        return True
    return snapshot.max_recent_video_views >= subscribers * ratio


class YouTubeCollector:
    """Toda a comunicação com a YouTube Data API v3.

    Contabiliza as unidades gastas (`units_consumed`, gravado em
    `collection_runs.api_units_consumed`), respeita um orçamento por execução e
    rotaciona entre as chaves configuradas quando uma delas esgota a cota diária.
    """

    def __init__(
        self,
        api_keys: list[str] | None = None,
        quota_budget: int | None = None,
        service_factory: Callable[[str], Any] | None = None,
    ) -> None:
        keys = list(api_keys) if api_keys is not None else settings.youtube_api_key_pool
        if not keys:
            raise ValueError(
                "Nenhuma chave da YouTube Data API configurada (YOUTUBE_API_KEY/YOUTUBE_API_KEYS)."
            )
        self._api_keys = keys
        self._key_index = 0
        self._service_factory = service_factory or _default_service_factory
        self._service: Any | None = None
        self._quota_budget = quota_budget
        self.units_consumed = 0
        # Cache de um canal só: `fetch_snapshot` e `fetch_recent_content_signals` são
        # chamados em sequência para o mesmo canal, e sem isso pagaríamos a cota duas
        # vezes. Um único slot mantém o uso de memória constante ao varrer milhares
        # de canais.
        self._bundle_cache: tuple[str, dict | None] | None = None

    # -- infraestrutura de chamada -------------------------------------------------

    def _service_now(self) -> Any:
        if self._service is None:
            self._service = self._service_factory(self._api_keys[self._key_index])
        return self._service

    def _rotate_key(self) -> bool:
        if self._key_index + 1 >= len(self._api_keys):
            return False
        self._key_index += 1
        self._service = None
        logger.warning(
            "Cota esgotada na chave %d; rotacionando para a chave %d de %d",
            self._key_index,
            self._key_index + 1,
            len(self._api_keys),
        )
        return True

    def _execute(self, build_request: Callable[[Any], Any], cost: int) -> dict:
        if self._quota_budget is not None and self.units_consumed + cost > self._quota_budget:
            raise QuotaExceededError(
                f"Orçamento de cota da execução esgotado ({self.units_consumed}/{self._quota_budget} unidades)."
            )
        while True:
            try:
                response = build_request(self._service_now()).execute()
            except HttpError as error:
                if _is_quota_error(error):
                    if self._rotate_key():
                        continue
                    raise QuotaExceededError(
                        "Cota diária esgotada em todas as chaves configuradas."
                    ) from error
                raise
            self.units_consumed += cost
            return response

    # -- descoberta ----------------------------------------------------------------

    def discover_candidates(self, niche_keywords: list[str]) -> list[ChannelRef]:
        """Descobre canais candidatos para um nicho (search.list, 100 unidades).

        As keywords do nicho são combinadas em uma única query com o operador OR (`|`)
        justamente para gastar 100 unidades por nicho, e não por keyword.
        """
        query = "|".join(keyword.strip() for keyword in niche_keywords if keyword.strip())
        if not query:
            return []

        published_after = datetime.now(timezone.utc) - timedelta(
            days=settings.discovery_video_window_days
        )
        response = self._execute(
            lambda service: service.search().list(
                part="snippet",
                q=query,
                type="video",
                order="viewCount",
                publishedAfter=published_after.isoformat().replace("+00:00", "Z"),
                regionCode=settings.youtube_region_code,
                maxResults=50,
            ),
            SEARCH_LIST_COST,
        )
        return self._refs_from_video_items(response.get("items", []))

    def discover_trending_candidates(self, category_ids: list[str] | None = None) -> list[ChannelRef]:
        """Descoberta barata via vídeos em alta (videos.list chart=mostPopular, 1 unidade).

        Complementa `discover_candidates` sem consumir cota de busca.
        """
        categories: list[str | None] = list(
            category_ids if category_ids is not None else settings.trending_category_ids
        )
        refs: dict[str, ChannelRef] = {}
        for category_id in categories or [None]:
            params: dict[str, Any] = {
                "part": "snippet",
                "chart": "mostPopular",
                "regionCode": settings.youtube_region_code,
                "maxResults": 50,
            }
            if category_id:
                params["videoCategoryId"] = category_id
            response = self._execute(
                lambda service, p=params: service.videos().list(**p), VIDEOS_LIST_COST
            )
            for ref in self._refs_from_video_items(response.get("items", [])):
                refs.setdefault(ref.youtube_channel_id, ref)
        return list(refs.values())

    @staticmethod
    def _refs_from_video_items(items: list[dict]) -> list[ChannelRef]:
        refs: dict[str, ChannelRef] = {}
        for item in items:
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId")
            if not channel_id:
                continue
            refs.setdefault(
                channel_id,
                ChannelRef(
                    youtube_channel_id=channel_id,
                    display_name=snippet.get("channelTitle"),
                    url=_channel_url(channel_id, None),
                ),
            )
        return list(refs.values())

    # -- snapshot e sinais de conteúdo ---------------------------------------------

    def fetch_snapshot(self, channel_ref: ChannelRef) -> ChannelSnapshot | None:
        """Métricas atuais de um canal conhecido (3 unidades no total).

        Devolve None quando o canal não existe mais (excluído ou privado): quem chama
        marca `status = removed` sem apagar o histórico.
        """
        bundle = self._channel_bundle(channel_ref.youtube_channel_id)
        if bundle is None:
            return None

        item = bundle["channel"]
        videos = bundle["recent_videos"]
        statistics = item.get("statistics", {})
        hidden_subscribers = bool(statistics.get("hiddenSubscriberCount"))
        avg_views, engagement_rate, max_views = _aggregate_video_stats(videos)

        return ChannelSnapshot(
            channel_ref=_ref_from_channel_item(item),
            collected_at=datetime.now(timezone.utc),
            subscriber_count=None if hidden_subscribers else _to_int(statistics.get("subscriberCount")),
            total_view_count=_to_int(statistics.get("viewCount")),
            video_count=_to_int(statistics.get("videoCount")),
            avg_views_last_n_videos=avg_views,
            engagement_rate=engagement_rate,
            max_recent_video_views=max_views,
            raw_payload={"channel": item, "recent_videos": videos},
        )

    def fetch_recent_content_signals(self, channel_ref: ChannelRef) -> list[ContentSignal]:
        """Textos recentes do canal (descrição do canal + dos últimos vídeos).

        Reaproveita o que `fetch_snapshot` já buscou para o mesmo canal, então em um
        job de snapshot não custa cota adicional.
        """
        bundle = self._channel_bundle(channel_ref.youtube_channel_id)
        if bundle is None:
            return []

        item = bundle["channel"]
        ref = _ref_from_channel_item(item)
        signals: list[ContentSignal] = []

        channel_description = item.get("snippet", {}).get("description")
        if channel_description:
            signals.append(
                ContentSignal(
                    channel_ref=ref,
                    source="channel_description",
                    text=channel_description,
                    url=ref.url,
                    published_at=_parse_published_at(item.get("snippet", {}).get("publishedAt")),
                )
            )

        for video in bundle["recent_videos"]:
            video_id = video.get("id")
            snippet = video.get("snippet", {})
            published_at = _parse_published_at(snippet.get("publishedAt"))
            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
            for source, text in (
                ("video_title", snippet.get("title")),
                ("video_description", snippet.get("description")),
            ):
                if not text:
                    continue
                signals.append(
                    ContentSignal(
                        channel_ref=ref,
                        source=source,
                        text=text,
                        video_id=video_id,
                        url=video_url,
                        published_at=published_at,
                    )
                )
        return signals

    def _channel_bundle(self, channel_id: str) -> dict | None:
        if self._bundle_cache is not None and self._bundle_cache[0] == channel_id:
            return self._bundle_cache[1]

        response = self._execute(
            lambda service: service.channels().list(
                part="snippet,statistics,contentDetails", id=channel_id
            ),
            CHANNELS_LIST_COST,
        )
        items = response.get("items", [])
        bundle = None
        if items:
            bundle = {"channel": items[0], "recent_videos": self._recent_videos(items[0])}
        # Guarda inclusive o None, para não reconsultar um canal removido.
        self._bundle_cache = (channel_id, bundle)
        return bundle

    def _recent_videos(self, channel_item: dict) -> list[dict]:
        """Últimos vídeos via playlist de uploads (1 unidade) + videos.list (1 unidade).

        É a alternativa barata ao `search.list` filtrado por canal, que custaria 100.
        """
        uploads_playlist_id = (
            channel_item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )
        if not uploads_playlist_id:
            return []

        try:
            playlist = self._execute(
                lambda service: service.playlistItems().list(
                    part="contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=settings.recent_videos_count,
                ),
                PLAYLIST_ITEMS_LIST_COST,
            )
        except HttpError as error:
            if error.resp.status == 404:
                # Canal sem uploads públicos: não é erro de coleta.
                return []
            raise

        video_ids = [
            item.get("contentDetails", {}).get("videoId")
            for item in playlist.get("items", [])
            if item.get("contentDetails", {}).get("videoId")
        ]
        if not video_ids:
            return []

        # videos.list aceita até 50 IDs por chamada, sempre por 1 unidade.
        videos = self._execute(
            lambda service: service.videos().list(
                part="snippet,statistics", id=",".join(video_ids[:50])
            ),
            VIDEOS_LIST_COST,
        )
        return videos.get("items", [])
