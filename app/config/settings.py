from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings with support for multiple LLM providers."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Configuration
    app_name: str = "Backend Architect API"
    app_version: str = "1.0.0"
    debug: bool = False

    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_temperature: float = 0.7
    anthropic_max_tokens: int = 2000

    # Google Configuration
    google_api_key: Optional[str] = None
    google_model: str = "gemini-2.0-flash"
    google_temperature: float = 0.7
    google_max_tokens: int = 2000

    # Default LLM Provider
    default_llm_provider: str = "openai"

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None  # anon key for client operations
    supabase_service_role_key: Optional[str] = None  # service role key for DB operations (bypasses RLS)
    jwt_secret: Optional[str] = None

    # Frontend Configuration
    frontend_url: str = "http://localhost:3000"
    auth_callback_url: str = "http://localhost:3000/auth/callback"

    # Crawler Configuration
    crawler_timeout: int = 30  # Seconds per page
    crawler_max_content_length: int = 50000  # Characters per page
    crawler_content_per_source: int = 8000  # Characters per source in LLM context
    crawler_max_concurrent: int = 5
    crawler_user_agent: str = "NuravBot/1.0 (+https://nurav.ai)"

    # Search Configuration
    default_search_engine: str = "duckduckgo"
    search_max_results: int = 5

    # Playwright Configuration
    playwright_headless: bool = True
    playwright_browser: str = "chromium"

    # Vector Databases - Pinecone (Academic Papers)
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "us-east1-gcp"
    pinecone_academic_index: str = "nurav-academic-papers"

    # YouTube Data API
    youtube_api_key: Optional[str] = None

    # Agentic Model Overrides (cost-efficient models for internal operations)
    classifier_provider: str = "openai"
    classifier_model: str = "gpt-4o-mini"
    synthesizer_provider: str = "openai"
    synthesizer_model: str = "gpt-4o-mini"

    # Agentic Query Timeouts (seconds)
    query_timeout_simple: int = 5
    query_timeout_research: int = 15
    query_timeout_deep: int = 30

    def get_llm_config(self, provider: str) -> dict:
        """Get configuration for a specific LLM provider."""
        configs = {
            "openai": {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
                "temperature": self.openai_temperature,
                "max_tokens": self.openai_max_tokens,
            },
            "anthropic": {
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
                "temperature": self.anthropic_temperature,
                "max_tokens": self.anthropic_max_tokens,
            },
            "google": {
                "api_key": self.google_api_key,
                "model": self.google_model,
                "temperature": self.google_temperature,
                "max_tokens": self.google_max_tokens,
            }
        }
        return configs.get(provider, {})


# Global settings instance
settings = Settings()
