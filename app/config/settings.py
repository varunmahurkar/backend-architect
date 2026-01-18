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
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_temperature: float = 0.7
    anthropic_max_tokens: int = 2000

    # Google Configuration
    google_api_key: Optional[str] = None
    google_model: str = "gemini-1.5-pro"
    google_temperature: float = 0.7
    google_max_tokens: int = 2000

    # Default LLM Provider
    default_llm_provider: str = "openai"

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    jwt_secret: Optional[str] = None

    # Frontend Configuration
    frontend_url: str = "http://localhost:3000"
    auth_callback_url: str = "http://localhost:3000/auth/callback"

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
