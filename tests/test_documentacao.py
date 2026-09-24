"""Guardas contra documentação que mente sobre o sistema.

O projeto tem uma regra explícita (`docs/10`, "Processo de ajuste"): nunca
alterar código de forma que a documentação passe a mentir sobre o comportamento
real. Regra escrita não se cumpre sozinha — na revisão de 2026-09-24 havia uma
coluna fora do `docs/03` e nove configurações fora do `.env.example`.

Estes testes não julgam se a documentação está *boa*; só travam o desvio que dá
para verificar mecanicamente. São baratos e não dependem de banco.
"""

import pathlib

import src.db.models  # noqa: F401 - registra as tabelas no metadata
from src.config.settings import Settings
from src.db.base import Base

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _secao_da_tabela(doc: str, tabela: str) -> str:
    inicio = doc.index(f"## `{tabela}`")
    fim = doc.find("\n## ", inicio + 1)
    return doc[inicio : fim if fim != -1 else len(doc)]


def test_toda_tabela_do_banco_esta_no_modelo_de_dados():
    """Uma tabela que existe no código e não no doc é uma tabela que ninguém
    além de quem a escreveu sabe que existe."""
    doc = (RAIZ / "docs" / "03-modelo-de-dados.md").read_text(encoding="utf-8")

    ausentes = [nome for nome in Base.metadata.tables if f"## `{nome}`" not in doc]

    assert not ausentes, f"tabelas fora de docs/03: {ausentes}"


def test_toda_coluna_do_banco_esta_no_modelo_de_dados():
    """Coluna nova em tabela antiga é o desvio mais fácil de deixar passar:
    o doc continua parecendo certo, só está incompleto."""
    doc = (RAIZ / "docs" / "03-modelo-de-dados.md").read_text(encoding="utf-8")

    desvios = {}
    for nome, tabela in Base.metadata.tables.items():
        if f"## `{nome}`" not in doc:
            continue
        secao = _secao_da_tabela(doc, nome)
        faltando = [c.name for c in tabela.columns if f"| {c.name} " not in secao]
        if faltando:
            desvios[nome] = faltando

    assert not desvios, f"colunas fora de docs/03: {desvios}"


def test_toda_configuracao_esta_no_env_example():
    """`CLAUDE.md` exige manter o .env.example atualizado a cada variável nova.
    Sem isso, quem for subir o sistema descobre a configuração faltando só
    quando o comportamento sai errado em produção."""
    exemplo = (RAIZ / ".env.example").read_text(encoding="utf-8")

    ausentes = [campo for campo in Settings.model_fields if campo.upper() not in exemplo]

    assert not ausentes, f"configurações fora do .env.example: {ausentes}"


def test_o_numero_de_telas_documentadas_bate_com_o_app():
    """A Tela 6 nasceu na Fase 9; se uma tela entrar sem doc (ou sair sem sumir
    do doc), o `docs/06` deixa de servir como especificação."""
    doc = (RAIZ / "docs" / "06-dashboard.md").read_text(encoding="utf-8")
    app = (RAIZ / "src" / "dashboard" / "app.py").read_text(encoding="utf-8")

    documentadas = doc.count("\n## Tela ")
    implementadas = app.count("st.Page(")

    assert documentadas == implementadas, (
        f"{documentadas} telas em docs/06 contra {implementadas} no app"
    )
