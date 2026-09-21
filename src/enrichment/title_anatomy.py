"""Anatomia do título — passo DISSECAR da metodologia Brecha Viral.

Quebra o título de um vídeo nas peças que fazem um formato funcionar, no mesmo
molde de `monetization.py`: regras explícitas (regex + listas), evidência
sempre anexada, nada de caixa-preta (docs/09).

**Multilíngue de propósito.** A metodologia existe justamente para levar um
formato de um idioma para outro; uma heurística só em português seria cega
exatamente onde ela precisa enxergar. Os títulos já coletados incluem
português, inglês e espanhol.

Cobertura: **PT, EN, ES, DE, IT, PL** — os seis idiomas dos mercados
decididos em `docs/00b`. Um idioma fora dessa lista faz o sistema dizer
"nenhuma peça reconhecida" quando na verdade não sabe ler: silêncio que parece
resposta. Ao abrir mercado novo, o vocabulário entra antes.

**Limite conhecido:** a comparação é por palavra exata, então idiomas muito
flexionados (polonês, alemão) perdem formas declinadas — "policjanta" não casa
com "policjant". Isso é subdetecção, que é o lado seguro do erro: casar por
prefixo pegaria as flexões, mas também faria "sem" casar dentro de "sempre",
e falso positivo com evidência anexada é pior que silêncio.

Especificação: `docs/05-motor-monetizacao-e-score.md`, seção "Anatomia do
título".
"""

import re
import unicodedata
from dataclasses import dataclass

from src.config.settings import settings

EVIDENCE_MAX_CHARS = 120

# Um título pode ter várias peças ao mesmo tempo — é justamente o empilhamento
# delas que faz o formato funcionar. As listas são propositalmente disjuntas
# entre si para a mesma palavra não contar duas vezes com sentidos diferentes.
VOCABULARIO = {
    "autoridade_emprestada": [
        # PT
        "policial", "policiais", "medico", "medicos", "medica", "enfermeiro",
        "advogado", "advogados", "especialista", "especialistas", "engenheiro",
        "professor", "professores", "cientista", "cientistas", "psicologo",
        "nutricionista", "veterinario", "bombeiro", "piloto", "juiz",
        "ex-policial", "ex-funcionario", "aposentado", "aposentados",
        # EN
        "police", "officer", "officers", "doctor", "doctors", "nurse", "lawyer",
        "expert", "experts", "engineer", "scientist", "scientists", "professor",
        "psychologist", "veterinarian", "firefighter", "pilot", "judge",
        "former", "retired", "navy seal", "ex-cop",
        # ES
        "policia", "policias", "abogado", "experto", "expertos", "ingeniero",
        "cientifico", "enfermera", "jubilado",
        # DE
        "polizist", "polizisten", "arzt", "arzte", "anwalt", "experte",
        "experten", "ingenieur", "wissenschaftler", "rentner", "ehemaliger",
        # IT
        "poliziotto", "poliziotti", "medici", "avvocato", "esperto", "esperti",
        "ingegnere", "professore", "scienziato", "pensionato",
        # PL
        "policjant", "policjanci", "lekarz", "lekarze", "prawnik", "ekspert",
        "eksperci", "inzynier", "naukowiec", "emeryt",
    ],
    "gatilho_medo": [
        # PT
        "nunca", "jamais", "erro", "erros", "perigo", "perigoso", "cuidado",
        "evite", "risco", "golpe", "armadilha", "roubo", "ladrao", "ladroes",
        "alerta", "grave", "fatal", "morte", "morrer", "prejuizo",
        # EN
        "never", "mistake", "mistakes", "danger", "dangerous", "warning",
        "avoid", "risk", "scam", "trap", "thief", "thieves", "deadly", "fatal",
        "death", "die", "worst",
        # ES
        "nunca", "error", "peligro", "peligroso", "evita", "riesgo", "estafa",
        "ladron", "ladrones", "muerte", "peor",
        # DE
        "nie", "niemals", "fehler", "gefahr", "gefahrlich", "achtung",
        "vermeiden", "risiko", "betrug", "falle", "dieb", "diebe", "todlich",
        "schlimmste",
        # IT
        "mai", "errore", "errori", "pericolo", "pericoloso", "attenzione",
        "evita", "rischio", "truffa", "trappola", "ladro", "ladri", "mortale",
        "peggiore",
        # PL
        "nigdy", "blad", "bledy", "niebezpieczenstwo", "uwaga", "unikaj",
        "ryzyko", "oszustwo", "pulapka", "zlodziej", "smiertelny", "najgorszy",
    ],
    "gatilho_desejo": [
        # PT
        "ganhe", "ganhar", "economize", "economizar", "dobre", "dobrar",
        "aumente", "aumentar", "melhore", "melhorar", "rico", "riqueza",
        "lucro", "lucrar", "dinheiro", "gratis", "barato", "rapido", "facil",
        # EN
        "earn", "save", "double", "boost", "increase", "improve", "rich",
        "wealth", "profit", "money", "free", "cheap", "fast", "easy",
        # ES
        "gana", "ganar", "ahorra", "ahorrar", "duplica", "aumenta", "rico",
        "riqueza", "dinero", "gratis", "barato", "rapido", "facil",
        # DE
        "verdienen", "sparen", "verdoppeln", "erhohen", "verbessern", "reich",
        "reichtum", "gewinn", "geld", "kostenlos", "billig", "schnell",
        # IT
        "guadagna", "risparmia", "raddoppia", "aumenta", "migliora", "ricco",
        "ricchezza", "profitto", "soldi", "economico", "veloce",
        # PL
        "zarabiaj", "oszczedzaj", "zwieksz", "popraw", "bogaty", "bogactwo",
        "zysk", "pieniadze", "darmo", "tani", "szybko", "latwo",
    ],
    "gatilho_curiosidade": [
        # PT
        "segredo", "segredos", "ninguem", "verdade", "revelado", "revelou",
        "descobri", "descobriram", "escondido", "escondem", "por que",
        "o que acontece", "voce sabia", "misterio", "bastidores", "na real",
        # EN
        "secret", "secrets", "nobody", "no one", "truth", "revealed", "reveals",
        "hidden", "they hide", "why", "what happens", "did you know", "mystery",
        "behind the scenes", "actually",
        # ES
        "secreto", "secretos", "nadie", "verdad", "revelado", "escondido",
        "por que", "que pasa", "sabias", "misterio",
        # DE
        "geheimnis", "geheime", "niemand", "wahrheit", "enthullt", "versteckt",
        "warum", "wusstest du", "ratsel",
        # IT
        "segreto", "segreti", "nessuno", "verita", "rivelato", "nascosto",
        "perche", "cosa succede", "lo sapevi", "mistero",
        # PL
        "sekret", "sekrety", "tajemnica", "nikt", "prawda", "ujawnione",
        "ukryte", "dlaczego", "czy wiesz",
    ],
    "promessa_negativa": [
        # Formulação por negação — costuma performar acima da afirmativa. Só
        # imperativos explícitos, para não colidir com gatilho_medo.
        "nao faca", "nao compre", "nao use", "pare de", "deixe de", "sem",
        # Primeira pessoa também é formato de negação, e é dos que mais
        # performam: "por que eu não uso mais X" é depoimento negativo.
        "nao uso", "nao recomendo", "nunca mais", "parei de", "deixei de",
        "dont", "do not", "stop", "quit", "without", "no more",
        "no hagas", "no compres", "deja de", "sin",
        "mach nicht", "kaufe nicht", "hor auf", "ohne",
        "non fare", "non comprare", "smetti di", "senza",
        "nie rob", "nie kupuj", "przestan", "bez",
    ],
}

# Confiança por tipo. Menor que a dos sinais de monetização de propósito: lá um
# domínio de afiliado é prova quase direta; aqui é leitura de vocabulário, que
# erra mais. `numero_alto` pontua acima por ser estrutural, não semântico.
CONFIANCA = {
    "numero_alto": 0.7,
    "autoridade_emprestada": 0.6,
    "gatilho_medo": 0.5,
    "gatilho_desejo": 0.45,
    "gatilho_curiosidade": 0.5,
    "promessa_negativa": 0.55,
}

# Número que quantifica a promessa ("25 esconderijos"). O token inclui separador
# de milhar: sem isso, em "R$3.847" o "3" era descartado por vir de moeda e o
# "847" entrava sozinho — falso positivo encontrado nos dados reais.
NUMERO = re.compile(r"(?<![\w$€£.,])(\d{1,3}(?:[.,]\d{3})+|\d{1,4})(?![\w%])")
ANO_MINIMO, ANO_MAXIMO = 1900, 2100

# Unidade logo depois do número indica medida, não contagem de lista: "65 anos"
# é idade, "500 reais" é preço. "25 esconderijos" é que é a promessa.
UNIDADES = {
    "ano", "anos", "mes", "meses", "dia", "dias", "hora", "horas", "minuto",
    "minutos", "segundo", "segundos", "semana", "semanas",
    "real", "reais", "dolar", "dolares", "euro", "euros", "mil", "milhao",
    "milhoes", "bilhao",
    "year", "years", "month", "months", "day", "days", "hour", "hours",
    "minute", "minutes", "second", "seconds", "week", "weeks",
    "dollar", "dollars", "kg", "km", "cm", "gb", "mb",
}


@dataclass(frozen=True)
class DetectedTitleSignal:
    signal_type: str
    evidence: str
    confidence: float


# O "ł" polonês é um caractere próprio (U+0142), não um "l" com diacrítico:
# o NFD não o decompõe, então precisa de tradução explícita. Sem isto, metade
# do vocabulário polonês nunca casaria.
_TRADUCOES = str.maketrans({"ł": "l", "Ł": "l", "ß": "ss", "ø": "o", "đ": "d"})


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento, para a lista não precisar de cada variação."""
    sem_acento = unicodedata.normalize("NFD", texto.lower().translate(_TRADUCOES))
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")


def _trecho(titulo: str, inicio: int, fim: int) -> str:
    """Recorte ao redor do match, ajustado para não cortar palavra no meio.

    Sem o ajuste a evidência saía como "tment Is a ZOO!" — num card cujo papel
    é ser prova conferível, isso parece defeito e mina a confiança no sinal.
    """
    esquerda = max(0, inicio - 25)
    if esquerda > 0:
        espaco = titulo.find(" ", esquerda, inicio)
        esquerda = espaco + 1 if espaco != -1 else esquerda
    direita = min(len(titulo), fim + 35)
    if direita < len(titulo):
        espaco = titulo.rfind(" ", fim, direita)
        direita = espaco if espaco != -1 else direita

    limpo = " ".join(titulo[esquerda:direita].split())
    return limpo if len(limpo) <= EVIDENCE_MAX_CHARS else f"{limpo[:EVIDENCE_MAX_CHARS]}…"


def _proxima_palavra(titulo: str, fim: int) -> str:
    resto = _normalizar(titulo[fim : fim + 30]).strip()
    return resto.split()[0].strip(".,:;!?") if resto.split() else ""


def _numero_alto(titulo: str) -> DetectedTitleSignal | None:
    for match in NUMERO.finditer(titulo):
        bruto = match.group(1).replace(".", "").replace(",", "")
        valor = int(bruto)
        if valor < settings.title_min_number:
            continue
        if ANO_MINIMO <= valor <= ANO_MAXIMO and len(bruto) == 4:
            continue  # data, não promessa quantificada
        if _proxima_palavra(titulo, match.end()) in UNIDADES:
            continue  # medida ("65 anos", "500 reais"), não contagem de lista
        return DetectedTitleSignal(
            signal_type="numero_alto",
            evidence=_trecho(titulo, match.start(), match.end()),
            confidence=CONFIANCA["numero_alto"],
        )
    return None


def detect_title_signals(titulo: str | None) -> list[DetectedTitleSignal]:
    """Peças reconhecidas no título, uma por tipo (a primeira ocorrência)."""
    if not titulo or not titulo.strip():
        return []

    sinais: list[DetectedTitleSignal] = []
    numero = _numero_alto(titulo)
    if numero:
        sinais.append(numero)

    normalizado = _normalizar(titulo)
    for signal_type, termos in VOCABULARIO.items():
        for termo in termos:
            # Fronteira de palavra: "sem" não pode casar dentro de "sempre".
            padrao = re.compile(rf"(?<!\w){re.escape(termo)}(?!\w)")
            match = padrao.search(normalizado)
            if match:
                sinais.append(
                    DetectedTitleSignal(
                        signal_type=signal_type,
                        # O trecho sai do título ORIGINAL, não do normalizado:
                        # quem confere precisa ver o texto como ele é de fato.
                        evidence=_trecho(titulo, match.start(), match.end()),
                        confidence=CONFIANCA[signal_type],
                    )
                )
                break
    return sinais
