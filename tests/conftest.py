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
