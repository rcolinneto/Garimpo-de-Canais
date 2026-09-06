"""Testes do motor de alertas (Fase 6).

Nenhum e-mail real é enviado: o envio é substituído por um espião. A regra de
"não notificar o mesmo evento duas vezes" é testada contra o Postgres real,
porque ela depende de comparar datas e scores em SQL — uma sessão falsa que
ignora filtros daria um teste que passa sem provar nada.
"""

import os
import smtplib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.db.models import AlertSent, Channel, ChannelScore, ChannelSnapshot, MonetizationSignal, Niche
from src.scheduler import alerts

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://garimpo:garimpo123@localhost:5433/garimpo")
AGORA = datetime.now(timezone.utc)


# --- espião de SMTP ---------------------------------------------------------


class SmtpFalso:
    """Substitui smtplib.SMTP, guardando as mensagens que passariam pela rede."""

    enviadas: list = []
    falhar = False

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, mensagem):
        if SmtpFalso.falhar:
            raise smtplib.SMTPException("servidor recusou")
        SmtpFalso.enviadas.append(mensagem)


@pytest.fixture(autouse=True)
def smtp_falso(monkeypatch):
    SmtpFalso.enviadas = []
    SmtpFalso.falhar = False
    monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
    monkeypatch.setattr(settings, "smtp_host", "smtp.exemplo.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "alert_email_from", "garimpo@exemplo.com")
    monkeypatch.setattr(settings, "alert_email_to", "chefe@exemplo.com")
    return SmtpFalso


# --- testes de envio (sem banco) --------------------------------------------


def test_email_de_alerta_chega_com_assunto_e_destinatario():
    enviado = alerts.enviar_email("[Garimpo] teste", "corpo do alerta")

    assert enviado is True
    assert len(SmtpFalso.enviadas) == 1
    assert SmtpFalso.enviadas[0]["Subject"] == "[Garimpo] teste"
    assert SmtpFalso.enviadas[0]["To"] == "chefe@exemplo.com"


def test_falha_de_envio_nao_levanta_excecao():
    SmtpFalso.falhar = True

    assert alerts.enviar_email("assunto", "corpo") is False


def test_sem_smtp_configurado_nao_tenta_enviar(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")

    assert alerts.smtp_configurado() is False
    assert alerts.enviar_email("assunto", "corpo") is False
    assert SmtpFalso.enviadas == []


def test_varios_destinatarios_separados_por_virgula(monkeypatch):
    monkeypatch.setattr(settings, "alert_email_to", "um@x.com, dois@x.com ")

    assert alerts.destinatarios() == ["um@x.com", "dois@x.com"]


def test_corpo_do_alerta_explica_o_score():
    canal = Channel(id=1, youtube_channel_id="UC1", display_name="Canal", url="https://y.t/c")
    score = ChannelScore(
        channel_id=1,
        calculated_at=AGORA,
        growth_score=10,
        monetization_score=20,
        niche_virality_score=5,
        total_score=72.5,
    )

    corpo = alerts._corpo_do_alerta(canal, score, limiar=50)

    assert "72.5" in corpo
    assert "limiar de score 50" in corpo
    # O chefe precisa do link para conferir o canal
    assert "https://y.t/c" in corpo


def test_falha_de_job_dispara_aviso_por_email():
    alerts.alertar_falha_de_job("snapshot", "erro qualquer")

    assert len(SmtpFalso.enviadas) == 1
    assert "Falha no job de snapshot" in SmtpFalso.enviadas[0]["Subject"]


def test_aviso_de_falha_nunca_propaga_erro(monkeypatch):
    def explodir(*args, **kwargs):
        raise RuntimeError("smtp fora do ar")

    monkeypatch.setattr(alerts, "enviar_email", explodir)

    # Não pode levantar: o job já falhou, o aviso não pode piorar a situação.
    alerts.alertar_falha_de_job("discovery", "erro qualquer")


# --- testes da regra de disparo (banco real) --------------------------------


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


def criar_canal(sessao, nome="Canal Teste") -> Channel:
    canal = Channel(
        youtube_channel_id=f"UC_{nome}", display_name=nome, status="active", url="https://y.t/c"
    )
    sessao.add(canal)
    sessao.flush()
    return canal


def criar_score(sessao, canal, total, quando=None) -> ChannelScore:
    score = ChannelScore(
        channel_id=canal.id,
        calculated_at=quando or AGORA,
        growth_score=10,
        monetization_score=20,
        niche_virality_score=5,
        total_score=total,
    )
    sessao.add(score)
    sessao.flush()
    return score


def test_canal_acima_do_limiar_entra_na_fila(sessao):
    canal = criar_canal(sessao)
    criar_score(sessao, canal, 80)

    pendentes = alerts.canais_para_alertar(sessao, limiar=50)

    assert [c.id for c, _ in pendentes] == [canal.id]


def test_canal_abaixo_do_limiar_nao_alerta(sessao):
    canal = criar_canal(sessao)
    criar_score(sessao, canal, 20)

    assert alerts.canais_para_alertar(sessao, limiar=50) == []


def test_canal_sem_score_nao_alerta(sessao):
    criar_canal(sessao)

    assert alerts.canais_para_alertar(sessao, limiar=50) == []


def test_nao_repete_alerta_enquanto_o_canal_continua_acima(sessao):
    canal = criar_canal(sessao)
    criar_score(sessao, canal, 80, AGORA - timedelta(days=3))
    sessao.add(
        AlertSent(
            channel_id=canal.id,
            triggered_at=AGORA - timedelta(days=2),
            reason="score 80 cruzou o limiar de 50",
            channel_out="email",
        )
    )
    # Continua acima depois do alerta: mesmo evento, não alerta de novo.
    criar_score(sessao, canal, 85)
    sessao.flush()

    assert alerts.canais_para_alertar(sessao, limiar=50) == []


def test_canal_que_caiu_e_voltou_a_cruzar_alerta_de_novo(sessao):
    canal = criar_canal(sessao)
    sessao.add(
        AlertSent(
            channel_id=canal.id,
            triggered_at=AGORA - timedelta(days=10),
            reason="score 80 cruzou o limiar de 50",
            channel_out="email",
        )
    )
    # Caiu abaixo depois do alerta e voltou a subir: evento novo.
    criar_score(sessao, canal, 20, AGORA - timedelta(days=5))
    criar_score(sessao, canal, 90)
    sessao.flush()

    assert [c.id for c, _ in alerts.canais_para_alertar(sessao, limiar=50)] == [canal.id]


def test_canal_removido_nao_alerta(sessao):
    canal = criar_canal(sessao)
    canal.status = "removed"
    criar_score(sessao, canal, 90)

    assert alerts.canais_para_alertar(sessao, limiar=50) == []


# --- job completo -----------------------------------------------------------


@pytest.fixture()
def job_na_sessao_de_teste(sessao, monkeypatch):
    """Faz run_alerts_job usar a sessão do teste em vez de abrir a sua própria."""

    class FabricaDeSessao:
        def __call__(self):
            return self

        def __enter__(self):
            return sessao

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(alerts, "SessionLocal", FabricaDeSessao())
    return sessao


def test_job_registra_alerta_como_email_quando_o_envio_funciona(job_na_sessao_de_teste):
    sessao = job_na_sessao_de_teste
    canal = criar_canal(sessao)
    criar_score(sessao, canal, 80)

    registrados = alerts.run_alerts_job(limiar=50)

    assert registrados == 1
    assert len(SmtpFalso.enviadas) == 1
    alerta = sessao.query(AlertSent).one()
    assert alerta.channel_out == "email"
    assert "cruzou o limiar de 50" in alerta.reason


def test_job_registra_dashboard_only_quando_o_email_falha(job_na_sessao_de_teste, monkeypatch):
    sessao = job_na_sessao_de_teste
    monkeypatch.setattr(settings, "smtp_host", "")  # SMTP não configurado
    canal = criar_canal(sessao)
    criar_score(sessao, canal, 80)

    registrados = alerts.run_alerts_job(limiar=50)

    # O alerta não se perde: fica registrado como visível só no dashboard.
    assert registrados == 1
    assert sessao.query(AlertSent).one().channel_out == "dashboard_only"


def test_job_rodado_duas_vezes_nao_duplica_alerta(job_na_sessao_de_teste):
    sessao = job_na_sessao_de_teste
    canal = criar_canal(sessao)
    criar_score(sessao, canal, 80)

    alerts.run_alerts_job(limiar=50)
    alerts.run_alerts_job(limiar=50)

    assert sessao.query(AlertSent).count() == 1
