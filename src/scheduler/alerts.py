"""Alertas por e-mail (Fase 6 do roadmap, Tela 5 de docs/06-dashboard.md).

Avisa quando um canal cruza o limiar de score configurado, sem repetir o mesmo
evento: enquanto o canal continuar acima do limiar, o alerta não é reenviado —
só volta a alertar se ele cair abaixo e cruzar de novo.

Também é o mecanismo usado para avisar sobre falha de job, exigido pelo
`docs/09-requisitos-nao-funcionais.md`.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from src.config.settings import settings
from src.db.models import AlertSent, Channel, ChannelScore
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)

CANAL_EMAIL = "email"
CANAL_DASHBOARD = "dashboard_only"


def destinatarios() -> list[str]:
    return [email.strip() for email in settings.alert_email_to.split(",") if email.strip()]


def smtp_configurado() -> bool:
    return bool(settings.smtp_host and settings.alert_email_from and destinatarios())


def enviar_email(assunto: str, corpo: str) -> bool:
    """Envia um e-mail simples. Devolve False (sem levantar) se não der.

    Um alerta que falha não pode derrubar o job que o disparou — o registro em
    `alerts_sent` marca `dashboard_only` e o dado continua visível no dashboard.
    """
    if not smtp_configurado():
        logger.warning("SMTP não configurado; alerta não será enviado por e-mail")
        return False

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = settings.alert_email_from
    mensagem["To"] = ", ".join(destinatarios())
    mensagem.set_content(corpo)

    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
                _autenticar_e_enviar(smtp, mensagem)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                _autenticar_e_enviar(smtp, mensagem)
    except (smtplib.SMTPException, OSError) as erro:
        logger.error("Falha ao enviar e-mail de alerta: %s", erro)
        return False

    logger.info("E-mail de alerta enviado para %s", mensagem["To"])
    return True


def _autenticar_e_enviar(smtp, mensagem: EmailMessage) -> None:
    if settings.smtp_user:
        smtp.login(settings.smtp_user, settings.smtp_password)
    smtp.send_message(mensagem)


def _ultimo_score(session, channel_id: int) -> ChannelScore | None:
    return (
        session.query(ChannelScore)
        .filter(ChannelScore.channel_id == channel_id)
        .order_by(ChannelScore.calculated_at.desc())
        .first()
    )


def _ja_alertado_para_este_evento(session, channel_id: int, limiar: float) -> bool:
    """True se o canal já foi alertado e não saiu do limiar desde então."""
    ultimo_alerta = (
        session.query(AlertSent)
        .filter(AlertSent.channel_id == channel_id)
        .order_by(AlertSent.triggered_at.desc())
        .first()
    )
    if ultimo_alerta is None:
        return False

    # Se em algum momento depois do alerta o canal caiu abaixo do limiar, uma nova
    # subida é um evento novo e merece alerta.
    caiu_depois = (
        session.query(ChannelScore)
        .filter(
            ChannelScore.channel_id == channel_id,
            ChannelScore.calculated_at > ultimo_alerta.triggered_at,
            ChannelScore.total_score < limiar,
        )
        .first()
    )
    return caiu_depois is None


def canais_para_alertar(session, limiar: float) -> list[tuple[Channel, ChannelScore]]:
    """Canais ativos acima do limiar que ainda não foram avisados para este evento."""
    pendentes = []
    for canal in session.query(Channel).filter(Channel.status == "active").all():
        score = _ultimo_score(session, canal.id)
        if score is None or score.total_score is None:
            continue
        if float(score.total_score) < limiar:
            continue
        if _ja_alertado_para_este_evento(session, canal.id, limiar):
            continue
        pendentes.append((canal, score))
    return pendentes


def _corpo_do_alerta(canal: Channel, score: ChannelScore, limiar: float) -> str:
    return (
        f"O canal {canal.display_name or canal.youtube_channel_id} cruzou o limiar de score {limiar}.\n\n"
        f"Score total: {float(score.total_score):.1f}\n"
        f"  crescimento: {float(score.growth_score or 0):.1f}\n"
        f"  monetização: {float(score.monetization_score or 0):.1f}\n"
        f"  viralidade do nicho: {float(score.niche_virality_score or 0):.1f}\n\n"
        f"Canal: {canal.url or '(sem link)'}\n\n"
        "Os sinais de monetização detectados e suas evidências estão no dashboard, "
        "na tela de detalhe do canal."
    )


def run_alerts_job(limiar: float | None = None) -> int:
    """Envia alertas dos canais que cruzaram o limiar. Devolve quantos foram registrados."""
    limiar = limiar if limiar is not None else settings.alert_score_threshold
    enviados = 0

    with SessionLocal() as session:
        pendentes = canais_para_alertar(session, limiar)
        for canal, score in pendentes:
            assunto = f"[Garimpo] {canal.display_name or canal.youtube_channel_id} cruzou score {limiar}"
            entregue = enviar_email(assunto, _corpo_do_alerta(canal, score, limiar))
            session.add(
                AlertSent(
                    channel_id=canal.id,
                    triggered_at=datetime.now(timezone.utc),
                    reason=f"score {float(score.total_score):.1f} cruzou o limiar de {limiar}",
                    # Sem SMTP o alerta não se perde: fica registrado como visível
                    # apenas no dashboard.
                    channel_out=CANAL_EMAIL if entregue else CANAL_DASHBOARD,
                )
            )
            enviados += 1
        session.commit()

    if enviados:
        logger.info("Alertas registrados: %d (limiar %.1f)", enviados, limiar)
    return enviados


def alertar_falha_de_job(job_type: str, error_message: str | None) -> None:
    """Aviso de job que falhou (docs/09) — nunca deixa o erro escapar."""
    try:
        enviar_email(
            f"[Garimpo] Falha no job de {job_type}",
            f"O job de {job_type} falhou.\n\nErro: {error_message or 'sem detalhe'}\n\n"
            "Verifique a tabela collection_runs e os logs da aplicação.",
        )
    except Exception:  # noqa: BLE001
        logger.exception("Não foi possível avisar sobre a falha do job de %s", job_type)
