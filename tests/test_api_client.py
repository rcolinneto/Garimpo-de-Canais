"""Testes do cliente HTTP do dashboard, em especial o tratamento de erros.

Cobre o bug real encontrado em produção: quando o serviço da API está
dormindo (comum no free tier do Render) e o proxy da hospedagem responde com
uma página HTML de erro (502/503/504) em vez de JSON, o cliente não pode
repassar esse HTML cru para a tela — só a mensagem amigável.
"""

from types import SimpleNamespace

import pytest

from src.dashboard import api_client
from src.dashboard.api_client import ApiError


def _resposta_html_de_erro(status_code: int) -> SimpleNamespace:
    corpo_html = (
        '<!DOCTYPE html><html><head><title>502</title>'
        '<style>@font-face{src:url("data:font/woff2;base64,AAAA")}</style>'
        "</head><body>Bad Gateway</body></html>"
    )

    def _json():
        raise ValueError("não é JSON")

    return SimpleNamespace(status_code=status_code, json=_json, text=corpo_html)


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_resposta_html_de_gateway_vira_mensagem_amigavel(monkeypatch, status_code):
    monkeypatch.setattr(
        api_client.requests, "request", lambda *a, **k: _resposta_html_de_erro(status_code)
    )

    with pytest.raises(ApiError) as excinfo:
        api_client.health()

    mensagem = str(excinfo.value)
    assert "<!DOCTYPE html>" not in mensagem
    assert "base64" not in mensagem
    assert "aguarde alguns segundos" in mensagem.lower()


def test_resposta_nao_json_generica_nao_vaza_corpo_cru(monkeypatch):
    monkeypatch.setattr(
        api_client.requests, "request", lambda *a, **k: _resposta_html_de_erro(418)
    )

    with pytest.raises(ApiError) as excinfo:
        api_client.health()

    mensagem = str(excinfo.value)
    assert "<!DOCTYPE html>" not in mensagem
    assert "Erro HTTP 418" in mensagem
