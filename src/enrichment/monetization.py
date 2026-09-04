"""Detecção de sinais de monetização (docs/05-motor-monetizacao-e-score.md).

Não existe API que diga "este canal monetiza": o motor infere por evidência
indireta e **sempre guarda a evidência**, para o chefe conferir manualmente antes
de decidir qualquer coisa. São regras (regex + listas de domínios), não ML:
explicáveis, baratas e fáceis de ajustar quando surgir um padrão novo de link.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from src.collectors.models import ChannelSnapshot, ContentSignal
from src.config.settings import settings

# Distância máxima, em caracteres, para considerar que uma palavra-chave está
# "próxima de um link" — o que separa "vendo um curso" de só falar de curso.
PROXIMITY_CHARS = 200
EVIDENCE_MAX_CHARS = 300

URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]}]+", re.IGNORECASE)

AGGREGATOR_DOMAINS = {
    "linktr.ee",
    "linktree.com",
    "beacons.ai",
    "beacons.page",
    "bio.link",
    "withkoji.com",
    "koji.to",
    "stan.store",
    "campsite.bio",
    "linkbio.co",
    "allmylinks.com",
}

AFFILIATE_DOMAINS = {
    "amzn.to",
    "hotmart.com",
    "hotm.art",
    "eduzz.com",
    "monetizze.com.br",
    "mon.net.br",
    "kiwify.com.br",
    "kiwify.app",
    "kiwify.com",
    "shopee.com.br",
    "shope.ee",
    "awin1.com",
    "lomadee.com",
    "braip.com",
    "ticto.app",
    "greenn.com.br",
}

STORE_DOMAINS = {
    "myshopify.com",
    "shopify.com",
    "lojaintegrada.com.br",
    "nuvemshop.com.br",
    "lojavirtualnuvem.com.br",
    "yampi.com.br",
    "cartpanda.com",
    "shopify.com.br",
}

PAID_COMMUNITY_DOMAINS = {
    "patreon.com",
    "apoia.se",
    "padrim.com.br",
    "buymeacoffee.com",
    "ko-fi.com",
    "catarse.me",
}

INFOPRODUCT_PATTERN = re.compile(
    r"\b(curso|mentoria|e-?book|aulas?|workshop|imers(?:ã|a)o|treinamento|masterclass|consultoria)\b",
    re.IGNORECASE,
)
SPONSORSHIP_PATTERN = re.compile(
    r"(#ad\b|#publi\b|\bpubli\b|\bpublipost\b|parceria paga|patrocinado por|publieditorial|\bpublicidade paga\b)",
    re.IGNORECASE,
)
PAID_COMMUNITY_PATTERN = re.compile(
    r"\b(assinatura|clube de membros|clube exclusivo|grupo vip|comunidade paga|área de membros|area de membros)\b",
    re.IGNORECASE,
)

# Confiança fixa por regra: link de afiliado direto é evidência forte; uma palavra
# solta como "curso", sem link junto, é evidência fraca.
CONFIDENCE = {
    "link_afiliado": 0.9,
    "loja_propria": 0.85,
    "comunidade_paga_link": 0.8,
    "infoproduto_com_link": 0.7,
    "link_agregador": 0.6,
    "patrocinio_mencionado": 0.5,
    "elegivel_parceria_plataforma": 0.5,
    "comunidade_paga_texto": 0.45,
    "infoproduto_texto": 0.4,
}


@dataclass(frozen=True)
class DetectedSignal:
    signal_type: str
    evidence: str
    confidence: float


def _host_of(url: str) -> str:
    candidate = url if "://" in url else f"https://{url}"
    host = (urlparse(candidate).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches_domain(host: str, domains: set[str]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _trim(text: str) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= EVIDENCE_MAX_CHARS else f"{clean[:EVIDENCE_MAX_CHARS]}…"


def _snippet_around(text: str, start: int, end: int) -> str:
    return _trim(text[max(0, start - 80) : min(len(text), end + 120)])


def _classify_url(url: str) -> tuple[str, float] | None:
    """Classifica um link em um tipo de sinal, ou None se for um link qualquer."""
    host = _host_of(url)
    if not host:
        return None
    if _matches_domain(host, AFFILIATE_DOMAINS):
        return "link_afiliado", CONFIDENCE["link_afiliado"]
    # Amazon só conta como afiliado quando carrega a tag de associado.
    if "amazon." in host and re.search(r"[?&]tag=", url, re.IGNORECASE):
        return "link_afiliado", CONFIDENCE["link_afiliado"]
    if _matches_domain(host, STORE_DOMAINS):
        return "loja_propria", CONFIDENCE["loja_propria"]
    if _matches_domain(host, PAID_COMMUNITY_DOMAINS):
        return "comunidade_paga", CONFIDENCE["comunidade_paga_link"]
    if _matches_domain(host, AGGREGATOR_DOMAINS):
        return "link_agregador", CONFIDENCE["link_agregador"]
    return None


def _detect_in_text(text: str) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    url_spans = [(match.start(), match.end(), match.group()) for match in URL_PATTERN.finditer(text)]

    for _, _, url in url_spans:
        classified = _classify_url(url)
        if classified:
            signal_type, confidence = classified
            signals.append(DetectedSignal(signal_type, _trim(url), confidence))

    for match in INFOPRODUCT_PATTERN.finditer(text):
        near_link = any(
            start - PROXIMITY_CHARS <= match.start() <= end + PROXIMITY_CHARS
            for start, end, _ in url_spans
        )
        confidence = (
            CONFIDENCE["infoproduto_com_link"] if near_link else CONFIDENCE["infoproduto_texto"]
        )
        signals.append(
            DetectedSignal("infoproduto", _snippet_around(text, match.start(), match.end()), confidence)
        )

    for match in SPONSORSHIP_PATTERN.finditer(text):
        signals.append(
            DetectedSignal(
                "patrocinio_mencionado",
                _snippet_around(text, match.start(), match.end()),
                CONFIDENCE["patrocinio_mencionado"],
            )
        )

    for match in PAID_COMMUNITY_PATTERN.finditer(text):
        signals.append(
            DetectedSignal(
                "comunidade_paga",
                _snippet_around(text, match.start(), match.end()),
                CONFIDENCE["comunidade_paga_texto"],
            )
        )

    return signals


def _platform_partnership_signal(snapshot: ChannelSnapshot) -> DetectedSignal | None:
    """Elegibilidade ao YouTube Partner Program pelo critério público de inscritos.

    Só dá para verificar o limiar de inscritos: horas assistidas não são expostas
    pela API, então a evidência deixa explícito que a checagem é parcial.
    """
    subscribers = snapshot.subscriber_count
    if subscribers is None or subscribers < settings.ypp_min_subscribers:
        return None
    return DetectedSignal(
        "elegivel_parceria_plataforma",
        (
            f"{subscribers} inscritos (≥ {settings.ypp_min_subscribers} exigidos pelo YPP). "
            "Horas assistidas não são verificáveis pela API."
        ),
        CONFIDENCE["elegivel_parceria_plataforma"],
    )


def dedupe_key(signal_type: str, evidence: str) -> tuple[str, str]:
    """Chave de deduplicação de um sinal.

    URLs são normalizadas (protocolo, `www.`, barra final e caixa do domínio) para
    que o mesmo link não vire dois sinais só por aparecer como http em um vídeo e
    https em outro.
    """
    normalized = evidence.strip()
    if URL_PATTERN.fullmatch(normalized):
        normalized = re.sub(r"^https?://", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"^www\.", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.rstrip("/")
        host, _, path = normalized.partition("/")
        normalized = f"{host.lower()}/{path}" if path else host.lower()
    return signal_type, normalized


def detect_signals(
    content_signals: Iterable[ContentSignal],
    snapshot: ChannelSnapshot | None = None,
) -> list[DetectedSignal]:
    """Roda todas as regras sobre os textos recentes do canal.

    Deduplica por (tipo, evidência): o mesmo link repetido em dez vídeos é um
    sinal só, não dez.
    """
    found: dict[tuple[str, str], DetectedSignal] = {}

    for content in content_signals:
        for signal in _detect_in_text(content.text):
            key = dedupe_key(signal.signal_type, signal.evidence)
            # Mantém a maior confiança quando a mesma evidência aparece em contextos diferentes.
            if key not in found or signal.confidence > found[key].confidence:
                found[key] = signal

    if snapshot is not None:
        partnership = _platform_partnership_signal(snapshot)
        if partnership:
            found[dedupe_key(partnership.signal_type, partnership.evidence)] = partnership

    return sorted(found.values(), key=lambda signal: signal.confidence, reverse=True)
