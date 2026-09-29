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

# Só o que a tela usa: o endereço da API, a senha e o token de escrita. Nada de
# credencial de banco, chave do YouTube ou SMTP — quem precisa disso é a API,
# que roda em outro lugar.
#
# A lista é explícita e não um "copia tudo" porque é ela que garante que um
# segredo colocado aqui por engano não vire variável de ambiente do dashboard.
# O preço é que um segredo novo precisa ser somado aqui à mão — foi o que quase
# aconteceu com o API_WRITE_TOKEN, que sem esta linha seria configurado no
# Streamlit e mesmo assim nunca chegaria ao `settings`, deixando a Tela 4 em 401
# sem nenhuma pista do motivo.
for chave in ("API_BASE_URL", "DASHBOARD_PASSWORD", "API_WRITE_TOKEN"):
    if chave in segredos:
        os.environ[chave] = str(segredos[chave])

from src.dashboard.app import main  # noqa: E402 - depende do bloco acima

main()
