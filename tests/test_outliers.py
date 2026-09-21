"""Testes do motor de outlier (Fase 7 — passo GARIMPAR da Brecha Viral).

Lógica pura, sem banco: o que se testa aqui é a regra de comparação, que é o
que decide quais vídeos o chefe vê primeiro.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.config.settings import settings
from src.enrichment.outliers import (
    VideoParaOutlier,
    calcular_baseline,
    calcular_outlier,
    e_short,
    peso_de_recencia,
)
from src.scheduler.videos import duracao_em_segundos, extrair_videos

AGORA = datetime(2026, 9, 21, tzinfo=timezone.utc)


def video(vid, views, dias_atras=30, duracao=600):
    return VideoParaOutlier(
        youtube_video_id=vid,
        view_count=views,
        published_at=AGORA - timedelta(days=dias_atras),
        duration_seconds=duracao,
    )


def test_video_na_media_do_canal_nao_e_outlier():
    canal = [video(f"v{i}", 10_000) for i in range(5)]

    resultado = calcular_outlier(canal[0], canal, AGORA)

    assert resultado["outlier_ratio"] == pytest.approx(1.0)
    assert resultado["outlier_score"] == 0.0


def test_o_proprio_video_nao_entra_na_media_que_o_julga():
    """Sem excluir, o pico infla a média que deveria julgá-lo — e quanto maior
    o pico, mais ele se esconde. Este teste trava esse comportamento."""
    canal = [video(f"v{i}", 10_000) for i in range(4)]
    pico = video("pico", 100_000, dias_atras=2)

    baseline, detalhe = calcular_baseline(canal + [pico], pico)

    assert baseline == 10_000, "a média deve ser a dos outros vídeos, sem o pico"
    assert detalhe["videos_comparados"] == 4


def test_short_so_compara_com_short():
    """Misturar Short com vídeo longo produz outlier fantasma: as distribuições
    de views não são comparáveis."""
    longos = [video(f"L{i}", 1_000_000, duracao=900) for i in range(3)]
    shorts = [video(f"S{i}", 10_000, duracao=45) for i in range(3)]
    short_alvo = video("S_alvo", 30_000, duracao=45)

    baseline, detalhe = calcular_baseline(longos + shorts + [short_alvo], short_alvo)

    assert baseline == 10_000, "deve comparar só com os outros Shorts"
    assert detalhe["classe"] == "short"


def test_duracao_desconhecida_e_marcada_no_breakdown():
    """Vídeos recuperados do histórico não têm duração. Comparar com todos é
    aceitável, desde que fique explícito que foi isso que aconteceu."""
    canal = [video(f"v{i}", 10_000, duracao=None) for i in range(3)]
    alvo = VideoParaOutlier("alvo", 50_000, AGORA - timedelta(days=5), None)

    resultado = calcular_outlier(alvo, canal + [alvo], AGORA)

    assert resultado["breakdown"]["baseline"]["duracao_conhecida"] is False
    assert resultado["breakdown"]["baseline"]["classe"] == "duração desconhecida"


def test_recencia_prioriza_o_pico_de_agora():
    """Mesmo pico, idades diferentes: o recente é oportunidade, o antigo é
    história — quem chega depois não chega primeiro."""
    canal = [video(f"v{i}", 10_000, dias_atras=90) for i in range(4)]
    recente = video("recente", 60_000, dias_atras=3)
    antigo = video("antigo", 60_000, dias_atras=240)

    score_recente = calcular_outlier(recente, canal + [recente], AGORA)["outlier_score"]
    score_antigo = calcular_outlier(antigo, canal + [antigo], AGORA)["outlier_score"]

    assert score_recente > score_antigo * 5
    assert peso_de_recencia(AGORA, AGORA) == pytest.approx(1.0)
    # O piso impede que um outlier antigo desapareça: ele ainda prova o formato.
    assert peso_de_recencia(AGORA - timedelta(days=3650), AGORA) == settings.outlier_recency_floor


def test_sem_comparacao_possivel_devolve_none_e_nao_zero():
    """"Não dá para comparar" e "está na média" são coisas diferentes; gravar
    zero apagaria essa distinção."""
    sozinho = video("unico", 50_000)

    assert calcular_outlier(sozinho, [sozinho], AGORA) is None
    assert calcular_outlier(VideoParaOutlier("x", None, AGORA, 600), [sozinho], AGORA) is None


def test_classificacao_de_short():
    assert e_short(45) is True
    assert e_short(900) is False
    assert e_short(None) is None


@pytest.mark.parametrize(
    "iso,esperado",
    [("PT1M30S", 90), ("PT15S", 15), ("PT1H2M3S", 3723), ("P1DT2H", 93600), (None, None), ("xx", None)],
)
def test_duracao_iso_para_segundos(iso, esperado):
    assert duracao_em_segundos(iso) == esperado


def test_extrai_videos_do_payload_antigo_sem_duracao():
    """Payloads coletados antes da Fase 7 não têm contentDetails. O extrator
    precisa aceitá-los, senão o backfill do histórico não funciona."""
    payload = {
        "recent_videos": [
            {
                "id": "abc",
                "snippet": {"title": "Vídeo antigo", "publishedAt": "2026-09-01T10:00:00Z"},
                "statistics": {"viewCount": "5000"},
            }
        ]
    }

    [extraido] = extrair_videos(payload)

    assert extraido["youtube_video_id"] == "abc"
    assert extraido["view_count"] == 5000
    assert extraido["duration_seconds"] is None
    assert extraido["published_at"].year == 2026


def test_extrai_videos_ignora_item_sem_id():
    assert extrair_videos({"recent_videos": [{"snippet": {"title": "sem id"}}]}) == []
    assert extrair_videos(None) == []


def test_base_minuscula_nao_vira_outlier():
    """Achado ao validar com dados reais: um vídeo de 4.173 views num canal que
    faz 380 aparecia em 1º lugar. Onze vezes uma base minúscula não prova que o
    formato funciona — mesmo raciocínio do growth_min_base."""
    canal = [video(f"v{i}", 380) for i in range(4)]
    modesto = video("modesto", 4_173, dias_atras=3)

    resultado = calcular_outlier(modesto, canal + [modesto], AGORA)

    assert resultado["breakdown"]["piso_aplicado"] is True
    assert resultado["outlier_score"] == 0.0


def test_escala_log_preserva_a_diferenca_entre_grandes_outliers():
    """Antes, 1155x e 11x empatavam no teto e só a recência os separava."""
    canal = [video(f"v{i}", 20_000) for i in range(4)]
    grande = video("grande", 200_000, dias_atras=3)
    gigante = video("gigante", 5_000_000, dias_atras=3)

    s_grande = calcular_outlier(grande, canal + [grande], AGORA)["outlier_score"]
    s_gigante = calcular_outlier(gigante, canal + [gigante], AGORA)["outlier_score"]

    assert s_gigante > s_grande, "o outlier maior tem de pontuar mais"
    assert s_grande > 0
    # Compressão: 25x mais views não vale 25x mais nota.
    assert s_gigante < s_grande * 3
