from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # YouTube Data API v3
    youtube_api_key: str = ""
    # Pool adicional de chaves (separado por vírgula) para rotacionar quando uma
    # chave estourar a cota diária — ver docs/04-coleta-youtube.md.
    youtube_api_keys: str = ""
    youtube_region_code: str = "BR"
    # IDs de categoria usados na descoberta barata por "vídeos em alta"
    # (vazio = tendências gerais da região).
    youtube_trending_category_ids: str = ""

    database_url: str = "postgresql://garimpo:garimpo@localhost:5433/garimpo"
    dashboard_password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_from: str = ""
    alert_email_to: str = ""

    # Agendamento dos jobs (cron de 5 campos)
    scheduler_enabled: bool = True
    discovery_cron: str = "0 3 * * *"
    snapshot_cron: str = "0 5 * * *"

    # Orçamento de cota por execução (total diário da chave é 10.000 unidades)
    discovery_quota_budget: int = 3000
    snapshot_quota_budget: int = 6000

    # Descoberta
    discovery_niches_per_run: int = 5
    discovery_video_window_days: int = 30
    discovery_max_subscribers: int = 100_000
    discovery_min_view_subscriber_ratio: float = 1.0

    # Quantos vídeos recentes são analisados por canal em cada snapshot
    recent_videos_count: int = 10

    @property
    def youtube_api_key_pool(self) -> list[str]:
        """Chaves disponíveis, na ordem de uso (YOUTUBE_API_KEY primeiro)."""
        keys = [key.strip() for key in self.youtube_api_keys.split(",") if key.strip()]
        if self.youtube_api_key and self.youtube_api_key not in keys:
            keys.insert(0, self.youtube_api_key)
        return keys

    @property
    def trending_category_ids(self) -> list[str]:
        return [c.strip() for c in self.youtube_trending_category_ids.split(",") if c.strip()]


settings = Settings()
