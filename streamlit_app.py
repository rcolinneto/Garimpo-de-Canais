"""Ponto de entrada do dashboard no Streamlit Community Cloud.

Existe por duas razões, ambas de ordem — e as duas quebram o app se ignoradas.

1. Caminho de import. O app real é `src/dashboard/app.py` e importa `src.*`,
   mas o Streamlit coloca no `sys.path` a pasta do arquivo de entrada: apontar
   direto para `src/dashboard/app.py` deixaria a raiz do projeto de fora. Com o
   arquivo de entrada aqui na raiz, `src` fica importável sem mexer no path.
   No Docker isso não aparece porque lá o pacote é instalado (`pip install .`).

2. Segredos antes do import. No Community Cloud os segredos chegam via
   `st.secrets`, e só viram variáveis de ambiente quando esse objeto é lido
   pela primeira vez. Só que `settings` (pydantic-settings) lê o ambiente no
   instante em que `src.config.settings` é importado — que acontece dentro do
   import de `src.dashboard.app`. Sem a cópia explícita abaixo, o import
   ganha a corrida e o app sobe sem senha configurada, recusando o login com
   "DASHBOARD_PASSWORD não configurada" (foi exatamente o que aconteceu no
   primeiro deploy).
"""

import os

import streamlit as st

try:
    segredos = dict(st.secrets)
except Exception:  # noqa: BLE001
    # Nenhum arquivo de segredos: é o caso de rodar fora do Community Cloud
    # (local ou Docker), onde a configuração vem do .env. O Streamlit levanta
    # StreamlitSecretNotFoundError aqui — confirmado testando, não suposto.
    segredos = {}

# Só o que a tela usa: a API e a senha. Nada de credencial de banco, chave do
# YouTube ou SMTP — quem precisa disso é a API, que roda em outro lugar.
for chave in ("API_BASE_URL", "DASHBOARD_PASSWORD"):
    if chave in segredos:
        os.environ[chave] = str(segredos[chave])

from src.dashboard.app import main  # noqa: E402 - depende do bloco acima

main()
