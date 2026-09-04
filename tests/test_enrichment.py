from datetime import datetime, timedelta, timezone

import pytest

from src.collectors.models import ChannelRef, ChannelSnapshot, ContentSignal
from src.enrichment.monetization import detect_signals
from src.enrichment.scoring import (
    calculate_growth_score,
    calculate_monetization_score,
    calculate_total_score,
)

REF = ChannelRef(youtube_channel_id="UC123", display_name="Canal Teste")


def content(text, source="video_description"):
    return ContentSignal(channel_ref=REF, source=source, text=text)


def tipos(signals):
    return {signal.signal_type for signal in signals}


def por_tipo(signals, signal_type):
    return [signal for signal in signals if signal.signal_type == signal_type]


def test_detecta_link_de_afiliado():
    signals = detect_signals([content("Compre aqui: https://hotmart.com/pt-br/curso-abc")])

    afiliados = por_tipo(signals, "link_afiliado")
    assert len(afiliados) == 1
    assert afiliados[0].confidence == 0.9
    assert "hotmart.com" in afiliados[0].evidence


def test_amazon_so_conta_como_afiliado_com_tag_de_associado():
    com_tag = detect_signals([content("https://www.amazon.com.br/dp/B08?tag=meucanal-20")])
    sem_tag = detect_signals([content("https://www.amazon.com.br/dp/B08")])

    assert "link_afiliado" in tipos(com_tag)
    assert "link_afiliado" not in tipos(sem_tag)


def test_detecta_agregador_loja_e_comunidade_paga():
    signals = detect_signals(
        [
            content("Meus links: https://linktr.ee/canal"),
            content("Loja: https://minhaloja.myshopify.com"),
            content("Apoie: https://www.patreon.com/canal"),
        ]
    )

    assert {"link_agregador", "loja_propria", "comunidade_paga"} <= tipos(signals)


def test_infoproduto_pesa_mais_quando_esta_perto_de_um_link():
    com_link = detect_signals([content("Meu curso completo: https://exemplo.com.br/inscricao")])
    sem_link = detect_signals([content("Nesse vídeo comento sobre o curso que fiz ano passado")])

    assert por_tipo(com_link, "infoproduto")[0].confidence == 0.7
    assert por_tipo(sem_link, "infoproduto")[0].confidence == 0.4


def test_detecta_patrocinio_sem_confundir_com_palavras_parecidas():
    detectado = detect_signals([content("Esse vídeo é #publi, patrocinado por uma marca")])
    falso_positivo = detect_signals([content("Vídeo publicado ontem para o público em geral")])

    assert "patrocinio_mencionado" in tipos(detectado)
    assert "patrocinio_mencionado" not in tipos(falso_positivo)


def test_evidencia_e_sempre_guardada_para_conferencia_manual():
    signals = detect_signals([content("Link: https://kiwify.com.br/produto-x")])

    assert all(signal.evidence for signal in signals)


def test_mesmo_link_repetido_vira_um_unico_sinal():
    repetido = "Compre: https://hotmart.com/curso"
    signals = detect_signals([content(repetido), content(repetido), content(repetido)])

    assert len(por_tipo(signals, "link_afiliado")) == 1


def test_mesmo_link_em_http_e_https_nao_vira_dois_sinais():
    signals = detect_signals(
        [
            content("Compre: http://pay.kiwify.com.br/08oRkkn"),
            content("Compre: https://pay.kiwify.com.br/08oRkkn/"),
            content("Compre: https://WWW.pay.kiwify.com.br/08oRkkn"),
        ]
    )

    assert len(por_tipo(signals, "link_afiliado")) == 1


def snapshot_pydantic(subscribers):
    return ChannelSnapshot(
        channel_ref=REF, collected_at=datetime.now(timezone.utc), subscriber_count=subscribers
    )


def test_elegibilidade_ao_ypp_usa_o_limiar_publico_de_inscritos():
    acima = detect_signals([], snapshot_pydantic(5_000))
    abaixo = detect_signals([], snapshot_pydantic(300))

    assert "elegivel_parceria_plataforma" in tipos(acima)
    assert "elegivel_parceria_plataforma" not in tipos(abaixo)
    # A evidência precisa deixar claro que horas assistidas não são verificáveis.
    assert "Horas assistidas" in por_tipo(acima, "elegivel_parceria_plataforma")[0].evidence


class FakeSnapshot:
    """Stand-in do modelo do banco, só com o que o cálculo de crescimento usa."""

    def __init__(self, collected_at, subscriber_count=None, total_view_count=None):
        self.collected_at = collected_at
        self.subscriber_count = subscriber_count
        self.total_view_count = total_view_count


def test_growth_score_normaliza_pela_janela_de_referencia():
    agora = datetime.now(timezone.utc)
    # +10% de inscritos em 7 dias, exatamente a janela padrão.
    atual = FakeSnapshot(agora, subscriber_count=11_000)
    anterior = FakeSnapshot(agora - timedelta(days=7), subscriber_count=10_000)

    score, detalhe = calculate_growth_score(atual, anterior)

    assert score == pytest.approx(10.0)
    assert detalhe["base"] == "inscritos"
    assert detalhe["dias_decorridos"] == pytest.approx(7.0)


def test_canal_minusculo_nao_domina_o_ranking_por_percentual():
    """+2 inscritos em um canal de 17 não pode valer mais que crescimento real."""
    agora = datetime.now(timezone.utc)
    minusculo = calculate_growth_score(
        FakeSnapshot(agora, subscriber_count=19),
        FakeSnapshot(agora - timedelta(hours=18), subscriber_count=17),
    )[0]
    relevante = calculate_growth_score(
        FakeSnapshot(agora, subscriber_count=11_000),
        FakeSnapshot(agora - timedelta(days=7), subscriber_count=10_000),
    )[0]

    assert minusculo < relevante


def test_extrapolacao_de_janela_curta_tem_teto():
    agora = datetime.now(timezone.utc)
    _, detalhe = calculate_growth_score(
        FakeSnapshot(agora, subscriber_count=11_000),
        FakeSnapshot(agora - timedelta(hours=6), subscriber_count=10_000),
    )

    # 7 dias / 0,25 dia daria fator 28; o teto segura em 3.
    assert detalhe["fator_normalizacao"] == pytest.approx(3.0)


def test_growth_score_penaliza_canal_grande():
    agora = datetime.now(timezone.utc)
    pequeno = calculate_growth_score(
        FakeSnapshot(agora, subscriber_count=11_000),
        FakeSnapshot(agora - timedelta(days=7), subscriber_count=10_000),
    )[0]
    grande = calculate_growth_score(
        FakeSnapshot(agora, subscriber_count=1_100_000),
        FakeSnapshot(agora - timedelta(days=7), subscriber_count=1_000_000),
    )[0]

    assert grande < pequeno


def test_growth_score_cai_para_views_quando_inscritos_estao_ocultos():
    agora = datetime.now(timezone.utc)
    atual = FakeSnapshot(agora, subscriber_count=None, total_view_count=2000)
    anterior = FakeSnapshot(agora - timedelta(days=7), subscriber_count=None, total_view_count=1000)

    score, detalhe = calculate_growth_score(atual, anterior)

    assert detalhe["base"] == "views"
    assert score > 0


def test_growth_score_e_zero_sem_historico_e_nunca_negativo():
    agora = datetime.now(timezone.utc)
    sem_historico, detalhe = calculate_growth_score(FakeSnapshot(agora, subscriber_count=100), None)
    queda, _ = calculate_growth_score(
        FakeSnapshot(agora, subscriber_count=800),
        FakeSnapshot(agora - timedelta(days=7), subscriber_count=1000),
    )

    assert sem_historico == 0.0
    assert "sem snapshot anterior" in detalhe["motivo"]
    assert queda == 0.0


class FakeSignal:
    def __init__(self, signal_type, confidence):
        self.signal_type = signal_type
        self.confidence = confidence


def test_monetization_score_pesa_sinais_fortes_acima_dos_fracos():
    forte, _ = calculate_monetization_score([FakeSignal("link_afiliado", 0.9)])
    fraco, _ = calculate_monetization_score([FakeSignal("patrocinio_mencionado", 0.9)])

    assert forte > fraco


def test_monetization_score_limitado_a_100():
    sinais = [FakeSignal("link_afiliado", 0.9) for _ in range(20)]

    score, detalhe = calculate_monetization_score(sinais)

    assert score == 100.0
    assert detalhe["sinais_considerados"] == 20


def test_total_score_combina_os_tres_componentes_com_os_pesos():
    total, pesos = calculate_total_score(100.0, 100.0, 100.0)

    assert total == pytest.approx(100.0)
    assert pesos == {"crescimento": 0.5, "monetizacao": 0.3, "nicho": 0.2}


def test_total_score_reflete_os_pesos_de_cada_componente():
    so_crescimento, _ = calculate_total_score(100.0, 0.0, 0.0)
    so_monetizacao, _ = calculate_total_score(0.0, 100.0, 0.0)

    assert so_crescimento == pytest.approx(50.0)
    assert so_monetizacao == pytest.approx(30.0)
