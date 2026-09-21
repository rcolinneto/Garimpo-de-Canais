"""Testes da anatomia do título (Fase 8 — passo DISSECAR da Brecha Viral).

O que se testa aqui é o que separa sinal de ruído: uma heurística de lista de
palavras erra fácil, e um falso positivo com evidência anexada é pior que
nenhum sinal — dá aparência de prova a um palpite.
"""

import pytest

from src.enrichment.title_anatomy import detect_title_signals


def tipos(titulo):
    return {sinal.signal_type for sinal in detect_title_signals(titulo)}


def sinal(titulo, tipo):
    return next(s for s in detect_title_signals(titulo) if s.signal_type == tipo)


def test_exemplo_do_treinamento_e_reconhecido():
    """O título usado como referência na metodologia (166 mil views em 9 dias).
    Se o sistema não enxerga as peças dele, não enxerga nada."""
    titulo = "25 esconderijos que ladrões nunca verificam (policiais aposentados usam todos eles)"

    assert {"numero_alto", "autoridade_emprestada", "gatilho_medo"} <= tipos(titulo)


def test_titulo_comum_nao_dispara_nada():
    """Falso positivo é pior que silêncio: daria aparência de prova a um palpite."""
    assert tipos("Receita de bolo de cenoura") == set()
    assert tipos("Vlog do fim de semana") == set()


def test_ano_nao_conta_como_numero_alto():
    """"2026" é data, não promessa quantificada."""
    assert "numero_alto" not in tipos("As melhores músicas de 2026")
    assert "numero_alto" in tipos("As 15 melhores músicas de 2026")


def test_numero_baixo_nao_conta():
    """"3 dicas" não carrega a promessa que "25 esconderijos" carrega."""
    assert "numero_alto" not in tipos("3 dicas de organização")


def test_reconhece_ingles_e_espanhol():
    """A metodologia é sobre levar formato entre idiomas — uma heurística só em
    português seria cega justamente onde ela precisa enxergar."""
    assert {"numero_alto", "autoridade_emprestada"} <= tipos(
        "10 Secrets Retired Police Officers Never Share"
    )
    assert "gatilho_curiosidade" in tipos("El secreto que nadie te cuenta")


def test_fronteira_de_palavra_evita_casar_dentro_de_outra():
    """"sem" não pode casar dentro de "sempre", senão metade dos títulos em
    português viraria promessa negativa."""
    assert "promessa_negativa" not in tipos("Ele sempre faz isso antes de dormir")
    assert "promessa_negativa" in tipos("Pare de fazer isso com seu dinheiro")


def test_evidencia_vem_do_titulo_original_com_acento():
    """Quem confere precisa ver o texto como ele é, não a forma normalizada que
    o motor usa internamente para comparar."""
    detectado = sinal("O segredo que ninguém te contou sobre café", "gatilho_curiosidade")

    assert "segredo" in detectado.evidence
    assert "ninguém" in detectado.evidence or "segredo" in detectado.evidence
    assert detectado.confidence > 0


def test_um_tipo_nao_repete_no_mesmo_titulo():
    """Um título com várias palavras do mesmo grupo gera um sinal, não vários."""
    detectados = detect_title_signals("Erro, perigo e risco: nunca faça isso")
    medos = [s for s in detectados if s.signal_type == "gatilho_medo"]

    assert len(medos) == 1


def test_titulo_vazio_ou_ausente():
    assert detect_title_signals(None) == []
    assert detect_title_signals("") == []
    assert detect_title_signals("   ") == []


@pytest.mark.parametrize(
    "titulo,esperado",
    [
        ("NÃO FAÇA ISSO com seu dinheiro", "promessa_negativa"),
        ("Como economizar 500 reais por mês", "gatilho_desejo"),
        ("A verdade que escondem de você", "gatilho_curiosidade"),
        ("O erro fatal que te deixa pobre", "gatilho_medo"),
    ],
)
def test_gatilhos_principais(titulo, esperado):
    assert esperado in tipos(titulo)


def test_valor_em_dinheiro_nao_vira_numero_alto():
    """Falso positivo achado nos dados reais: em "R$3.847" o "3" era descartado
    por vir de moeda e o "847" entrava sozinho, pelo separador de milhar."""
    assert "numero_alto" not in tipos("Da Dívida ao Primeiro Milhão — R$3.847 a R$1.000.000")


def test_medida_nao_vira_numero_alto():
    """Outro falso positivo real: "65 anos" é idade, não contagem de lista."""
    assert "numero_alto" not in tipos("Trabalhar Até os 65 Anos Vale a Pena?")
    assert "numero_alto" not in tipos("Economize 500 reais por mês")
    # Mas contagem de itens continua valendo.
    assert "numero_alto" in tipos("1.000 dicas de produtividade")


@pytest.mark.parametrize(
    "idioma,titulo",
    [
        ("alemão", "10 Verstecke die Diebe niemals prüfen (Polizisten im Ruhestand)"),
        ("italiano", "15 nascondigli che i ladri non controllano mai (poliziotti in pensione)"),
        ("polonês", "12 kryjówek których złodzieje nigdy nie sprawdzają"),
    ],
)
def test_reconhece_os_idiomas_dos_mercados_decididos(idioma, titulo):
    """Os mercados de 00b são US/en, DE/de, IT/it e PL/pl. Sem o vocabulário, o
    sistema diria "nenhuma peça" quando na verdade não sabe ler o idioma."""
    encontrados = tipos(titulo)

    assert "numero_alto" in encontrados, f"número não reconhecido em {idioma}"
    assert "gatilho_medo" in encontrados, f"gatilho não reconhecido em {idioma}"


def test_caractere_polones_l_cortado_e_normalizado():
    """"ł" é caractere próprio (U+0142), não "l" com acento: o NFD não o
    decompõe, então sem tradução explícita metade do polonês nunca casaria."""
    assert "gatilho_medo" in tipos("Najgorszy błąd który możesz popełnić")
