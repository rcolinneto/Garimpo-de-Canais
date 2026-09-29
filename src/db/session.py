from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import com_driver_explicito, settings

# O driver vai explícito na URL: o padrão do SQLAlchemy para `postgresql://`
# mudou na versão 2.1 e derrubou a API numa reconstrução de imagem.
engine = create_engine(com_driver_explicito(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
