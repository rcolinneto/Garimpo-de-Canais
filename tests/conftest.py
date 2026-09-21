"""Apoio compartilhado entre os testes.

O motivo de existir: vários testes de integração precisam do Postgres e, sem o
banco de pé, cada um gastava ~4s tentando conectar antes de pular. Com 45
testes nessa situação a suíte levava 4 minutos só para dizer "pulado". A
checagem agora é feita uma vez por URL e reaproveitada.
"""

from functools import lru_cache

from sqlalchemy import create_engine


@lru_cache(maxsize=None)
def erro_de_conexao(url: str) -> str | None:
    """Devolve a mensagem de erro ao conectar na URL, ou None se conectou."""
    try:
        create_engine(url).connect().close()
    except Exception as erro:  # noqa: BLE001 - qualquer falha aqui significa "sem banco"
        return str(erro)
    return None


# Ordem de limpeza das tabelas: filhos antes dos pais, senão a chave estrangeira
# bloqueia o delete. Fica aqui, num lugar só, porque três arquivos de teste
# precisam dela — quando as tabelas de vídeo entraram na Fase 7, cada cópia
# desatualizada quebrou a suíte inteira contra um banco que já tinha vídeos.
def modelos_para_limpar():
    from src.db.models import (
        AlertSent,
        Channel,
        ChannelScore,
        ChannelSnapshot,
        MonetizationSignal,
        Niche,
        TitleSignal,
        Video,
        VideoOutlier,
        VideoSnapshot,
    )

    return (
        TitleSignal,
        VideoOutlier,
        VideoSnapshot,
        Video,
        AlertSent,
        ChannelScore,
        MonetizationSignal,
        ChannelSnapshot,
        Channel,
        Niche,
    )
