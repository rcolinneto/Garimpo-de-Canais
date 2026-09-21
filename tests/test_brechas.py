"""Testes do score de oportunidade e do mapeamento de brechas (Fase 9).

O que se protege aqui são as decisões que a metodologia deixa explícitas e que
seriam fáceis de errar em silêncio: zero resultado não é brecha livre, RPM alto
não compensa mercado lotado, e a 4ª pergunta não entra na conta.
"""

import pytest

from src.config.settings import settings
from src.db.models import Video
from src.enrichment.opportunities import (
    SinaisDeMercado,
    calcular_opportunity_score,
    espaco_livre,
    rpm_normalizado,
)
from src.scheduler.brechas import CARTEIRA_INICIAL, _termo_de_busca

EUA = SinaisDeMercado(rpm_estimado=12.0, falantes_estimados=400_000_000)
POLONIA = SinaisDeMercado(rpm_estimado=6.0, falantes_estimados=40_000_000)


def test_nenhum_resultado_nao_e_brecha_livre():
    """O erro mais fácil de cometer aqui. Silêncio na busca pode significar que
    não há demanda naquele idioma (pergunta 1), e não que o espaço está livre
    (pergunta 2) — são conclusões opostas a partir do mesmo dado."""
    nota_vazio, detalhe = espaco_livre(0, 0, 0)
    nota_livre, _ = espaco_livre(10, 8, 2)

    assert nota_vazio == settings.espaco_livre_sem_resultado
    assert nota_vazio < nota_livre, "vazio não pode pontuar como espaço confirmado"
    assert "demanda" in detalhe["motivo"]


def test_espaco_livre_cresce_com_resultados_fracos():
    """Resultados antigos ou de canais pequenos = espaço aberto."""
    assert espaco_livre(10, 10, 0)[0] == 100.0
    assert espaco_livre(10, 0, 0)[0] == 0.0
    assert espaco_livre(10, 3, 2)[0] == pytest.approx(50.0)


def test_rpm_pondera_pelo_alcance():
    """A metodologia é explícita que é conta: CPM alto com poucos falantes pode
    render menos que CPM médio com muita gente."""
    assert rpm_normalizado(EUA)[0] > rpm_normalizado(POLONIA)[0]
    # Mercado pequeno e rico não zera: o piso de alcance preserva parte do valor.
    assert rpm_normalizado(POLONIA)[0] > 0


def test_sem_mercado_e_neutro_e_nao_zero():
    """Brecha só de ângulo (mesmo país do original) não tem mercado. Ausência
    de mercado não é demérito — pontuar zero a penalizaria indevidamente."""
    nota, detalhe = rpm_normalizado(None)

    assert nota == 50.0
    assert "ângulo" in detalhe["motivo"]


def test_mercado_livre_vence_mercado_rico_e_lotado():
    """O trade-off central da metodologia: espaço livre vale mais que CPM alto
    quando o CPM alto vem com todo mundo já lá dentro."""
    livre = espaco_livre(10, 8, 2)
    lotado = espaco_livre(10, 0, 0)

    polonia_livre = calcular_opportunity_score(80.0, POLONIA, livre[0], livre[1])
    eua_lotado = calcular_opportunity_score(80.0, EUA, lotado[0], lotado[1])

    assert polonia_livre["opportunity_score"] > eua_lotado["opportunity_score"]


def test_quarta_pergunta_fica_fora_da_formula_e_declarada():
    """Clima e cultura não são deriváveis das métricas. Fingir que são
    transformaria palpite em número com aparência de precisão."""
    resultado = calcular_opportunity_score(50.0, EUA, 50.0, {})

    assert "nao_avaliado" in resultado["breakdown"]
    assert "manualmente" in resultado["breakdown"]["nao_avaliado"]


def test_breakdown_mostra_cada_componente_com_seu_peso():
    """Requisito de explicabilidade (docs/09): o chefe precisa poder entender
    por que uma brecha está acima da outra."""
    resultado = calcular_opportunity_score(80.0, POLONIA, 70.0, {"resultados": 10})

    partes = resultado["breakdown"]
    assert {"outlier", "rpm", "espaco_livre"} <= set(partes)
    for parte in ("outlier", "rpm", "espaco_livre"):
        assert "peso" in partes[parte] and "score" in partes[parte]


def test_termo_de_busca_procura_o_assunto_nao_o_titulo_exato():
    """Procurar o título exato só acharia cópias dele — justamente o que a
    metodologia diz para não fazer."""
    termo = _termo_de_busca(Video(title="25 esconderijos que ladrões nunca verificam!"))

    assert "25" not in termo, "o número quantifica a promessa, não é o assunto"
    assert "esconderijos" in termo
    assert "!" not in termo


def test_carteira_inicial_bate_com_a_decisao_registrada():
    """Os mercados foram decididos em docs/00b: um de CPM alto e três de menor
    concorrência. Se a carteira mudar, a decisão precisa mudar junto."""
    codigos = {m["region_code"] for m in CARTEIRA_INICIAL}

    assert codigos == {"US", "DE", "IT", "PL"}
    for mercado in CARTEIRA_INICIAL:
        assert mercado["rpm_estimado"] > 0
        assert mercado["falantes_estimados"] > 0


def test_score_aceita_decimal_vindo_do_banco():
    """Bug real achado na validação de ponta a ponta: colunas Numeric do
    SQLAlchemy voltam como Decimal, que não divide com float. Os testes
    unitários não pegaram porque usavam float puro."""
    from decimal import Decimal

    mercado = SinaisDeMercado(rpm_estimado=float(Decimal("6.0")), falantes_estimados=40_000_000)

    resultado = calcular_opportunity_score(float(Decimal("80.0")), mercado, 70.0, {})

    assert resultado["opportunity_score"] > 0
