"""Cliente HTTP da API interna.

O dashboard nunca fala com o banco direto — toda leitura e escrita passa por
aqui, que é a regra arquitetural de `docs/02-arquitetura.md`: é o que permite
trocar a camada de apresentação depois sem reescrever o resto do sistema.
"""

import time
from typing import Any

import requests

from src.config.settings import settings

# 60s e não 30s: quando o serviço está subindo, a hospedagem segura a conexão
# aberta até o contêiner responder. Medido no Render, isso passou de 31s — com
# timeout de 30s a tentativa morria justo antes da resposta chegar, jogando
# fora o tempo que já tinha esperado.
TIMEOUT_SEGUNDOS = 60
# A busca sob demanda é síncrona e chama a API do YouTube na hora — pode levar
# bem mais que o timeout padrão para um nicho com muitos candidatos.
TIMEOUT_BUSCA_AGORA_SEGUNDOS = 180

# Hospedagem gratuita desliga o serviço da API depois de um tempo ocioso. A
# primeira chamada depois disso não falha de verdade: ela cai num 502/503/504
# do proxy (ou numa conexão recusada) durante as dezenas de segundos em que o
# contêiner está subindo, e funciona se for repetida. Em vez de mostrar um erro
# que "some sozinho quando você recarrega", esperamos a API acordar dentro
# desta janela e tentamos de novo — quem está usando só vê a tela demorar um
# pouco mais.
# 150s e não 90s: medindo o serviço real no Render, o tempo para subir variou
# de 22s a mais de 70s. A janela precisa cobrir o pior caso observado com
# folga, senão a espera termina num erro logo antes de a API ficar pronta.
ESPERA_MAXIMA_API_ACORDAR_SEGUNDOS = 150
INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS = 5
STATUS_API_ACORDANDO = (502, 503, 504)

# A janela acima vale por TELA, não por requisição. Cada tela faz várias
# chamadas (a "Visão Geral" faz 2, a "Detalhe do Canal" faz 3), e sem isto a
# espera se multiplica: medido com a API fora do ar, a "Visão Geral" levava
# 314s — 150s em cada chamada, em sequência — o que na prática é uma tela
# travada para sempre. Depois que uma chamada desiste, as seguintes falham na
# hora por este período, então a tela termina de renderizar e mostra o erro.
# Qualquer resposta da API zera esta memória.
MEMORIA_DE_DESISTENCIA_SEGUNDOS = 30
_ultima_desistencia: float | None = None


class ApiError(RuntimeError):
    """Erro vindo da API, já com a mensagem pronta para exibir na tela."""


def _url(path: str) -> str:
    return f"{settings.api_base_url.rstrip('/')}{path}"


def _tratar(resposta: requests.Response) -> Any:
    if resposta.status_code >= 400:
        try:
            detalhe = resposta.json().get("detail")
        except ValueError:
            # Resposta sem JSON — normalmente a página de erro do proxy da
            # hospedagem (não da nossa API), ex.: 502 enquanto o serviço `app`
            # ainda está acordando depois de ficar ocioso. Nunca repassar esse
            # HTML cru para a tela: além de poluído, pode conter uma fonte
            # inteira em base64.
            if resposta.status_code in (502, 503, 504):
                detalhe = (
                    "A API ainda está iniciando (comum após um período ocioso) — "
                    "aguarde alguns segundos e tente novamente."
                )
            else:
                detalhe = f"Erro HTTP {resposta.status_code} (resposta não veio em JSON)."
        if isinstance(detalhe, list):
            # Erro de validação do FastAPI (422): junta as mensagens de campo.
            detalhe = "; ".join(
                f"{'.'.join(str(parte) for parte in erro.get('loc', [])[1:])}: {erro.get('msg')}"
                for erro in detalhe
            )
        raise ApiError(detalhe or f"Erro HTTP {resposta.status_code}")
    return resposta.json()


def _desistiu_ha_pouco() -> bool:
    return (
        _ultima_desistencia is not None
        and time.monotonic() - _ultima_desistencia < MEMORIA_DE_DESISTENCIA_SEGUNDOS
    )


def _requisitar(metodo: str, path: str, timeout: float = TIMEOUT_SEGUNDOS, **kwargs) -> Any:
    global _ultima_desistencia

    # Se a chamada anterior já esperou a janela inteira e a API não voltou, não
    # adianta esta esperar tudo de novo: falha na hora para a tela conseguir
    # renderizar e mostrar o erro.
    espera = 0.0 if _desistiu_ha_pouco() else ESPERA_MAXIMA_API_ACORDAR_SEGUNDOS
    limite = time.monotonic() + espera
    while True:
        # Só vale insistir enquanto a janela de espera não estourou; passado
        # isso, o próximo resultado é o definitivo (vira erro na tela).
        insistir = time.monotonic() < limite
        try:
            resposta = requests.request(metodo, _url(path), timeout=timeout, **kwargs)
        except requests.RequestException as erro:
            if not insistir:
                _ultima_desistencia = time.monotonic()
                raise ApiError(
                    f"Não foi possível falar com a API ({settings.api_base_url}): {erro}"
                ) from erro
        else:
            if resposta.status_code not in STATUS_API_ACORDANDO or not insistir:
                # A API respondeu: esquece qualquer desistência anterior, senão
                # uma indisponibilidade passada penalizaria as telas seguintes.
                _ultima_desistencia = (
                    time.monotonic() if resposta.status_code in STATUS_API_ACORDANDO else None
                )
                return _tratar(resposta)
        time.sleep(INTERVALO_ENTRE_TENTATIVAS_SEGUNDOS)


def listar_canais(**filtros) -> dict:
    params = {chave: valor for chave, valor in filtros.items() if valor not in (None, "", [])}
    return _requisitar("GET", "/canais", params=params)


def detalhar_canal(channel_id: int) -> dict:
    return _requisitar("GET", f"/canais/{channel_id}")


def historico_canal(channel_id: int, days: int | None = None) -> dict:
    return _requisitar("GET", f"/canais/{channel_id}/historico", params={"days": days} if days else None)


def ranking_de_nichos() -> list[dict]:
    return _requisitar("GET", "/nichos/ranking")


def historico_do_nicho(niche_id: int, days: int = 90) -> list[dict]:
    return _requisitar("GET", f"/nichos/{niche_id}/historico", params={"days": days})


def criar_nicho(name: str, keywords: list[str], active: bool = True) -> dict:
    return _requisitar(
        "POST", "/nichos", json={"name": name, "keywords": keywords, "active": active}
    )


def atualizar_nicho(niche_id: int, **campos) -> dict:
    return _requisitar("PUT", f"/nichos/{niche_id}", json=campos)


def buscar_nicho_agora(niche_id: int) -> dict:
    """Dispara uma busca real no YouTube para o nicho, na hora — consome cota."""
    return _requisitar(
        "POST", f"/nichos/{niche_id}/buscar-agora", timeout=TIMEOUT_BUSCA_AGORA_SEGUNDOS
    )


def listar_alertas(limit: int = 100) -> list[dict]:
    return _requisitar("GET", "/alertas", params={"limit": limit})


def config_de_alertas() -> dict:
    return _requisitar("GET", "/alertas/config")


def listar_coletas(limit: int = 20) -> list[dict]:
    """Últimas rodadas de coleta — mostra se os jobs estão mesmo rodando."""
    return _requisitar("GET", "/coletas", params={"limit": limit})


def health() -> dict:
    return _requisitar("GET", "/health")
