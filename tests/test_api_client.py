"""Testes do cliente HTTP do dashboard, em especial o tratamento de erros.

Cobre o bug real encontrado em produção: quando o serviço da API está
dormindo (comum no free tier do Render) e o proxy da hospedagem responde com
uma página HTML de erro (502/503/504) em vez de JSON, o cliente não pode
repassar esse HTML cru para a tela — só a mensagem amigável.
"""

import time
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

    # headers sempre presente: uma resposta real tem, e o cliente lê Retry-After.
    return SimpleNamespace(status_code=status_code, headers={}, json=_json, text=corpo_html)


@pytest.fixture(autouse=True)
def sem_memoria_de_desistencia():
    """Zera o estado de módulo entre os testes.

    `_ultima_desistencia` é global de propósito (a API estar fora do ar é um
    fato do sistema, não de uma sessão), mas sem isto uma desistência de um
    teste faria o seguinte falhar na hora e o resultado dependeria da ordem.
    """
    api_client._ultima_desistencia = None
    yield
    api_client._ultima_desistencia = None


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
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {"status": "ok"}, text="")

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
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {"status": "ok"}, text="")

    monkeypatch.setattr(api_client.requests, "request", _request)

    assert api_client.health() == {"status": "ok"}
    assert len(chamadas) == 2


def test_erro_de_negocio_nao_fica_repetindo(monkeypatch, sem_espera):
    """Um 404 é resposta definitiva — insistir só atrasaria a tela."""
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        return SimpleNamespace(
            status_code=404, headers={}, json=lambda: {"detail": "Canal não encontrado"}, text=""
        )

    monkeypatch.setattr(api_client.requests, "request", _request)

    with pytest.raises(ApiError, match="Canal não encontrado"):
        api_client.detalhar_canal(1)
    assert len(chamadas) == 1


def test_janela_de_espera_e_por_tela_nao_por_requisicao(monkeypatch):
    """O bug que travava a tela: cada chamada esperava a janela inteira.

    Uma tela faz várias chamadas em sequência. Medido com a API fora do ar, a
    "Visão Geral" levava 314s e a "Detalhe do Canal" 471s — tela parada. Depois
    que uma chamada desiste, as seguintes têm de falhar na hora.
    """
    monkeypatch.setattr(api_client, "ESPERA_MAXIMA_API_ACORDAR_SEGUNDOS", 0.3)
    monkeypatch.setattr(api_client, "INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS", 0.05)
    monkeypatch.setattr(
        api_client.requests,
        "request",
        lambda *a, **k: (_ for _ in ()).throw(api_client.requests.ConnectionError("recusada")),
    )

    inicio = time.monotonic()
    with pytest.raises(ApiError):
        api_client.ranking_de_nichos()
    esperou = time.monotonic() - inicio

    inicio_segunda = time.monotonic()
    with pytest.raises(ApiError):
        api_client.listar_canais()
    segunda = time.monotonic() - inicio_segunda

    assert esperou >= 0.3, "a primeira chamada deve esperar a API acordar"
    assert segunda < esperou / 2, "a segunda não pode repetir a espera inteira"


def test_resposta_da_api_limpa_a_memoria_de_desistencia(monkeypatch):
    """Uma indisponibilidade passada não pode penalizar as telas seguintes."""
    monkeypatch.setattr(api_client, "INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS", 0)
    api_client._ultima_desistencia = time.monotonic()

    monkeypatch.setattr(
        api_client.requests,
        "request",
        lambda *a, **k: SimpleNamespace(status_code=200, headers={}, json=lambda: {"status": "ok"}, text=""),
    )

    assert api_client.health() == {"status": "ok"}
    assert api_client._ultima_desistencia is None


def test_429_e_esperado_em_vez_de_virar_erro(monkeypatch):
    """Achado em produção: "Erro HTTP 429" aparecia em TODAS as abas. 429 é a
    resposta canônica de "diminua o ritmo", não de "deu errado" — tratá-la como
    definitiva transformava um estrangulamento momentâneo em tela quebrada."""
    monkeypatch.setattr(api_client, "INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS", 0)
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 1:
            return SimpleNamespace(
                status_code=429, headers={}, json=lambda: {}, text="Too Many Requests"
            )
        return SimpleNamespace(
            status_code=200, headers={}, json=lambda: {"status": "ok"}, text=""
        )

    monkeypatch.setattr(api_client.requests, "request", _request)

    assert api_client.health() == {"status": "ok"}
    assert len(chamadas) == 2


def test_429_persistente_vira_mensagem_que_explica_o_que_fazer(monkeypatch, sem_espera):
    def _429(*args, **kwargs):
        def _json():
            raise ValueError("não é JSON")

        return SimpleNamespace(
            status_code=429, headers={}, json=_json, text="<html>429</html>"
        )

    monkeypatch.setattr(api_client.requests, "request", _429)

    with pytest.raises(ApiError) as excinfo:
        api_client.health()

    mensagem = str(excinfo.value)
    assert "<html>" not in mensagem
    assert "limitou o número de requisições" in mensagem
    assert "recarregue" in mensagem


def test_retry_after_do_servidor_e_obedecido(monkeypatch):
    """Ignorar o Retry-After e insistir no intervalo fixo é o que mantém o
    limite ativo por mais tempo."""
    esperas = []
    monkeypatch.setattr(api_client.time, "sleep", lambda s: esperas.append(s))
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 1:
            return SimpleNamespace(
                status_code=429, headers={"Retry-After": "7"}, json=lambda: {}, text=""
            )
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True}, text="")

    monkeypatch.setattr(api_client.requests, "request", _request)

    api_client.health()

    assert esperas == [7.0], "deve esperar o que o servidor pediu, não o intervalo padrão"


def test_retry_after_absurdo_e_limitado(monkeypatch):
    """Esperar minutos parado é pior que devolver o erro e deixar recarregar."""
    esperas = []
    monkeypatch.setattr(api_client.time, "sleep", lambda s: esperas.append(s))
    chamadas = []

    def _request(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 1:
            return SimpleNamespace(
                status_code=429, headers={"Retry-After": "3600"}, json=lambda: {}, text=""
            )
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {"ok": True}, text="")

    monkeypatch.setattr(api_client.requests, "request", _request)

    api_client.health()

    assert esperas == [api_client.ESPERA_MAXIMA_RETRY_AFTER_SEGUNDOS]
