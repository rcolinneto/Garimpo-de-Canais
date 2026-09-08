"""Testes do agendamento.

Existem porque o padrão do APScheduler descarta um job diário que perdeu a hora
(`misfire_grace_time` de 1 segundo): na prática o sistema ficava dias sem coletar
nada depois de a máquina suspender, sem nenhum aviso.
"""

from src.config.settings import settings
from src.scheduler.jobs import build_background_scheduler


def test_os_dois_jobs_diarios_sao_registrados():
    scheduler = build_background_scheduler()

    ids = {job.id for job in scheduler.get_jobs()}

    assert ids == {"discovery", "snapshot"}


def test_job_perdido_ainda_roda_quando_a_maquina_volta():
    scheduler = build_background_scheduler()

    for job in scheduler.get_jobs():
        assert job.misfire_grace_time == settings.scheduler_misfire_grace_seconds
        assert job.misfire_grace_time > 3600, "a janela precisa cobrir uma parada real"


def test_execucoes_perdidas_viram_uma_so():
    """Sem coalesce, voltar de dois dias parado dispararia dois jobs seguidos."""
    scheduler = build_background_scheduler()

    for job in scheduler.get_jobs():
        assert job.coalesce is True


def test_agendamento_usa_o_fuso_configurado():
    scheduler = build_background_scheduler()

    for job in scheduler.get_jobs():
        assert str(job.trigger.timezone) == settings.scheduler_timezone
