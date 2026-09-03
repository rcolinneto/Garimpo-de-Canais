from src.db.models import Niche
from src.db.session import SessionLocal

EXAMPLE_NICHES = [
    {
        "name": "finanças pessoais",
        "keywords": ["finanças pessoais", "investimentos para iniciantes", "sair das dívidas"],
    },
    {
        "name": "pets exóticos",
        "keywords": ["pets exóticos", "répteis de estimação", "aracnídeos de estimação"],
    },
    {
        "name": "produtividade e rotina",
        "keywords": ["produtividade", "rotina matinal", "organização pessoal"],
    },
]


def seed_niches() -> None:
    with SessionLocal() as session:
        for data in EXAMPLE_NICHES:
            exists = session.query(Niche).filter_by(name=data["name"]).first()
            if exists:
                continue
            session.add(Niche(name=data["name"], keywords=data["keywords"], active=True))
        session.commit()


if __name__ == "__main__":
    seed_niches()
