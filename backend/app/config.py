from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    frontend_origin: str
    environment: str = "production"
    shared_matching_enabled: bool = False
    local_ai_enabled: bool = False
    ollama_model: str = "qwen3:4b-instruct"
    ollama_model_digest: str = "unverified"
    local_ai_study_routes: str = ""
    cloud_ai_enabled: bool = False
    cloud_ai_sections: str = ""
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = "gemini-3.5-flash-lite"

    def __post_init__(self) -> None:
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        if self.environment != "development" and not self.frontend_origin.startswith("https://"):
            raise ValueError("FRONTEND_ORIGIN must use HTTPS outside development")

    @property
    def secure_cookies(self) -> bool:
        return self.environment != "development"

    @property
    def access_cookie(self) -> str:
        return "__Host-access" if self.secure_cookies else "dev-access"

    @property
    def refresh_cookie(self) -> str:
        return "__Host-refresh" if self.secure_cookies else "dev-refresh"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ["DATABASE_URL"],
            jwt_secret=os.environ["JWT_SECRET"],
            frontend_origin=os.environ["FRONTEND_ORIGIN"],
            environment=os.getenv("ENVIRONMENT", "production"),
            shared_matching_enabled=os.getenv("SHARED_MATCHING_ENABLED", "false").lower() == "true",
            local_ai_enabled=os.getenv("LOCAL_AI_ENABLED", "false").lower() == "true",
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct"),
            ollama_model_digest=os.getenv("OLLAMA_MODEL_DIGEST", "unverified"),
            local_ai_study_routes=os.getenv("LOCAL_AI_STUDY_ROUTES", ""),
            cloud_ai_enabled=os.getenv("CLOUD_AI_ENABLED", "false").lower() == "true",
            cloud_ai_sections=os.getenv("CLOUD_AI_SECTIONS", ""),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        )
