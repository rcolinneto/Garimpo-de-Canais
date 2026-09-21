"""Score de oportunidade — passos MAPEAR e VALIDAR da Brecha Viral.

Combina o que já foi medido, sem inventar dado novo:

```
opportunity_score = outlier_score      * peso_outlier
                  + rpm_normalizado    * peso_rpm
                  + espaco_livre_score * peso_concorrencia
```

A 4ª das "4 perguntas" da metodologia — *o assunto faz sentido nesse país?* —
**não entra na fórmula**. Clima, hábito e cultura não são deriváveis das
métricas que temos, e fingir que são transformaria um palpite num número com
aparência de precisão. Ela vive em `opportunities.notes`, como pendência
humana explícita.

Especificação: `docs/05-motor-monetizacao-e-score.md`.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config.settings import settings


@dataclass(frozen=True)
class SinaisDeMercado:
    """O que se sabe sobre um mercado na hora de pontuar uma brecha."""

    rpm_estimado: float | None
    falantes_estimados: int | None


def rpm_normalizado(mercado: SinaisDeMercado | None) -> tuple[float, dict]:
    """Nota de 0 a 100 para o retorno financeiro esperado do mercado.

    Pondera o RPM pelo alcance: a metodologia é explícita que é conta, não
    preferência — CPM alto com poucos falantes pode render menos que CPM médio
    com muita gente. Sem mercado definido (brecha só de ângulo, no mesmo país
    do original) devolve o valor neutro, não zero: ausência de mercado não é
    demérito.
    """
    if mercado is None:
        return 50.0, {"motivo": "brecha de ângulo, mesmo mercado do original"}
    if not mercado.rpm_estimado:
        return 50.0, {"motivo": "RPM não cadastrado para este mercado"}

    nota_rpm = min(100.0, mercado.rpm_estimado / settings.rpm_teto * 100)
    if not mercado.falantes_estimados:
        return nota_rpm, {"rpm": mercado.rpm_estimado, "alcance": "não cadastrado"}

    alcance = min(1.0, mercado.falantes_estimados / settings.falantes_referencia)
    # O alcance pesa, mas não anula: um mercado pequeno e rico continua valendo.
    nota = nota_rpm * (settings.peso_alcance_minimo + (1 - settings.peso_alcance_minimo) * alcance)
    return nota, {
        "rpm": mercado.rpm_estimado,
        "nota_rpm": round(nota_rpm, 2),
        "fator_alcance": round(alcance, 3),
        "falantes": mercado.falantes_estimados,
    }


def espaco_livre(
    resultados_encontrados: int,
    resultados_antigos: int,
    canais_pequenos: int,
) -> tuple[float, dict]:
    """Responde à pergunta 2: há canal atendendo esse assunto nesse idioma?

    Quanto mais os resultados forem antigos ou de canais pequenos, maior o
    espaço. Um detalhe que a metodologia deixa claro e é fácil errar: **zero
    resultado não é nota máxima**. Pode significar que não há demanda naquele
    idioma (pergunta 1), não que a brecha está livre — são conclusões opostas
    a partir do mesmo silêncio.
    """
    if resultados_encontrados == 0:
        return settings.espaco_livre_sem_resultado, {
            "motivo": "nenhum resultado — pode ser ausência de demanda, não brecha",
            "resultados": 0,
        }

    fracos = min(resultados_encontrados, resultados_antigos + canais_pequenos)
    proporcao = fracos / resultados_encontrados
    return min(100.0, proporcao * 100), {
        "resultados": resultados_encontrados,
        "antigos": resultados_antigos,
        "canais_pequenos": canais_pequenos,
        "proporcao_fraca": round(proporcao, 3),
    }


def calcular_opportunity_score(
    outlier_score: float | None,
    mercado: SinaisDeMercado | None,
    espaco_livre_score: float,
    detalhe_espaco: dict | None = None,
) -> dict:
    """Combina os três componentes com os pesos configurados."""
    outlier = float(outlier_score or 0.0)
    nota_rpm, detalhe_rpm = rpm_normalizado(mercado)

    total = (
        outlier * settings.peso_outlier
        + nota_rpm * settings.peso_rpm
        + espaco_livre_score * settings.peso_concorrencia
    )
    return {
        "opportunity_score": round(total, 4),
        "breakdown": {
            "outlier": {"score": round(outlier, 2), "peso": settings.peso_outlier},
            "rpm": {"score": round(nota_rpm, 2), "peso": settings.peso_rpm, **detalhe_rpm},
            "espaco_livre": {
                "score": round(espaco_livre_score, 2),
                "peso": settings.peso_concorrencia,
                **(detalhe_espaco or {}),
            },
            "nao_avaliado": (
                "Se o assunto faz sentido cultural neste país (4ª das 4 perguntas) "
                "não é derivável das métricas — conferir manualmente."
            ),
        },
    }
