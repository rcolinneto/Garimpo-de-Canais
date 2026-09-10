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


@pytest.fixture
def sem_espera(monkeypatch):
    """Zera a janela de espera para o teste não dormir esperando a API acordar."""
    monkeypatch.setattr(api_client, "ESPERA_MAXIMA_API_ACORDAR_SEGUNDOS", 0)
    monkeypatch.setattr(api_client, "INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS", 0)


@pytest.mark.parametrize("status_code", [502, 503, 504])
def test_resposta_html_de_gateway_vira_mensagem_amigavel(monkeypatch, sem_espera, status_code):
    monkeypatch.setattr(
        api_client.requests, "request", lambda *a, **k: _resposta_html_de_erro(status_code)
    )

    with pytest.raises(ApiError) as excinfo:
        api_client.health()

    mensagem = str(excinfo.value)
    assert "<!DOCTYPE html>" not in mensagem
    assert "base64" not in mensagem
    assert "aguarde alguns segundos" in mensagem.lower()


def test_resposta_nao_json_generica_nao_vaza_corpo_cru(monkeypatch, sem_espera):
    monkeypatch.setattr(
        api_client.requests, "request", lambda *a, **k: _resposta_html_de_erro(418)
    )

    with pytest.raises(ApiError) as excinfo:
        api_client.health()

    mensagem = str(excinfo.value)
    assert "<!DOCTYPE html>" not in mensagem
    assert "Erro HTTP 418" in mensagem


def test_api_acordando_e_esperada_em_vez_de_virar_erro(monkeypatch):
    """O caso real: a API está subindo, responde 502 duas vezes e depois funciona."""
    monkeypatch.setattr(api_client, "INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS", 0)
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) <= 2:
            return _resposta_html_de_erro(502)
        return SimpleNamespace(status_code=200, json=lambda: {"status": "ok"}, text="")

    monkeypatch.setattr(api_client.requests, "request", _request)

    assert api_client.health() == {"status": "ok"}
    assert len(chamadas) == 3


def test_erro_de_conexao_tambem_e_reesperado(monkeypatch):
    """Enquanto o contêiner sobe, a conexão é recusada antes de virar 502."""
    monkeypatch.setattr(api_client, "INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS", 0)
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise api_client.requests.ConnectionError("conexão recusada")
        return SimpleNamespace(status_code=200, json=lambda: {"status": "ok"}, text="")

    monkeypatch.setattr(api_client.requests, "request", _request)

    assert api_client.health() == {"status": "ok"}
    assert len(chamadas) == 2


def test_erro_de_negocio_nao_fica_repetindo(monkeypatch, sem_espera):
    """Um 404 é resposta definitiva — insistir só atrasaria a tela."""
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        return SimpleNamespace(
            status_code=404, json=lambda: {"detail": "Canal não encontrado"}, text=""
        )

    monkeypatch.setattr(api_client.requests, "request", _request)

    with pytest.raises(ApiError, match="Canal não encontrado"):
        api_client.detalhar_canal(1)
    assert len(chamadas) == 1
