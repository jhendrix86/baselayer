"""
BaseLayer Configuration Management

Handles all application configuration using Pydantic settings.
Environment variables are loaded and validated at startup.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings.
    
    All configuration is loaded from environment variables with sensible defaults.
    """
    
    # Application
    app_name: str = "BaseLayer"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Security
    secret_key: str = Field(env="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Database
    database_url: str = Field(env="DATABASE_URL")
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    
    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS"
    )
    
    # Ollama
    ollama_url: str = Field(default="http://localhost:11434", env="OLLAMA_URL")
    ollama_timeout: int = Field(default=30, env="OLLAMA_TIMEOUT")
    ollama_model: str = Field(default="qwen2.5-coder:3b", env="OLLAMA_MODEL")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    
    # Monitoring
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    
    # Governance
    governance_mode: str = Field(default="strict", env="GOVERNANCE_MODE")
    audit_enabled: bool = Field(default=True, env="AUDIT_ENABLED")
    
    # Performance
    max_request_size: int = Field(default=10 * 1024 * 1024, env="MAX_REQUEST_SIZE")  # 10MB
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # File Storage
    upload_dir: str = Field(default="/tmp/uploads", env="UPLOAD_DIR")
    max_file_size: int = Field(default=5 * 1024 * 1024, env="MAX_FILE_SIZE")  # 5MB
    
    @validator("cors_origins", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        """
        Parse CORS origins from string or list.
        """
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """
        Validate environment value.
        """
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """
        Validate log level.
        """
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"
    
    @property
    def database_url_sync(self) -> str:
        """
        Get synchronous database URL for migrations.
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings instance.
    
    Returns:
        Settings: Application configuration
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_database_url() -> str:
    """
    Get database URL from settings.
    
    Returns:
        str: Database connection URL
    """
    return get_settings().database_url


def get_redis_url() -> str:
    """
    Get Redis URL from settings.
    
    Returns:
        str: Redis connection URL
    """
    return get_settings().redis_url
