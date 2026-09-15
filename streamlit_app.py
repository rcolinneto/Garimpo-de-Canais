"""Ponto de entrada do dashboard no Streamlit Community Cloud.

Existe por causa do caminho de import. O app real é `src/dashboard/app.py` e
importa `src.*`, mas o Streamlit coloca no `sys.path` a pasta do arquivo de
entrada: apontar direto para `src/dashboard/app.py` deixaria a raiz do projeto
de fora e os imports quebrariam. Com o arquivo de entrada aqui na raiz, `src`
fica importável sem gambiarra de path.

No Docker isso não aparece porque lá o pacote é instalado (`pip install .`);
no Community Cloud as dependências vêm do requirements.txt, sem instalar o
projeto.
"""

from src.dashboard.app import main

main()
