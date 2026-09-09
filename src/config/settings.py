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
    # De onde o dashboard consome os dados (nunca do banco direto, ver docs/02)
    api_base_url: str = "http://localhost:8010"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    alert_email_from: str = ""
    # Aceita vários destinatários separados por vírgula
    alert_email_to: str = ""
    # Score a partir do qual um canal vira alerta
    alert_score_threshold: float = 50.0

    # Segredo compartilhado para disparar /cron/discovery e /cron/snapshot de
    # fora (ex.: GitHub Actions), usado quando não há como manter um processo
    # de agendamento sempre ligado (docs/07 — deploy gratuito em Render).
    cron_secret: str = ""

    # Agendamento dos jobs (cron de 5 campos)
    scheduler_enabled: bool = True
    discovery_cron: str = "0 3 * * *"
    snapshot_cron: str = "0 5 * * *"
    # Fuso do agendamento: sem isso o container roda em UTC e "3h" vira outro
    # horário para quem opera o sistema.
    scheduler_timezone: str = "America/Sao_Paulo"
    # Se a máquina estiver desligada/suspensa na hora marcada, o job ainda roda
    # quando o processo voltar dentro desta janela. Sem isso o padrão do
    # APScheduler é 1 segundo, ou seja: perdeu a hora, perdeu o dia.
    scheduler_misfire_grace_seconds: int = 21_600

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

    # Motor de score — pesos ajustáveis sem mexer em código (ex.: "dar mais peso
    # pra monetização"); devem somar 1.0.
    score_weight_growth: float = 0.5
    score_weight_monetization: float = 0.3
    score_weight_niche: float = 0.2
    # Janela de comparação de crescimento entre snapshots
    growth_comparison_days: int = 7
    # Piso do denominador da taxa: sem isso, +2 inscritos em um canal de 17 vira
    # "crescimento de 12%" e domina o ranking sobre canais realmente relevantes.
    growth_min_base: int = 1000
    # Teto da extrapolação quando a janela disponível é menor que a de referência,
    # para um único dia de sorte não virar uma taxa semanal explosiva.
    growth_max_normalization_factor: float = 3.0
    # Acima desse tamanho o canal já emergiu, então o crescimento pesa menos
    growth_large_channel_subscribers: int = 500_000
    growth_large_channel_factor: float = 0.5
    # Sinais de monetização considerados "ativos" e escala do componente
    monetization_window_days: int = 30
    monetization_score_scale: float = 25.0
    # Não regrava o mesmo sinal (tipo + evidência) detectado dentro desse período
    monetization_signal_dedupe_days: int = 30
    # Limiar público de inscritos do YouTube Partner Program
    ypp_min_subscribers: int = 1000

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
