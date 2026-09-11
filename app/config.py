"""配置中心：.env / 环境变量统一读取。"""
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class Settings:
    llm_api_key: str = field(default_factory=lambda: _get("LLM_API_KEY"))
    llm_base_url: str = field(default_factory=lambda: _get("LLM_BASE_URL", "https://api.deepseek.com/v1"))
    llm_model: str = field(default_factory=lambda: _get("LLM_MODEL", "deepseek-chat"))

    ocr_mode: str = field(default_factory=lambda: _get("OCR_MODE", "auto"))   # auto / mock / off

    mysql_host: str = field(default_factory=lambda: _get("MYSQL_HOST", "localhost"))
    mysql_port: int = int(_get("MYSQL_PORT", "3306"))
    mysql_user: str = field(default_factory=lambda: _get("MYSQL_USER", "root"))
    mysql_password: str = field(default_factory=lambda: _get("MYSQL_PASSWORD", "root"))
    mysql_db: str = field(default_factory=lambda: _get("MYSQL_DB", "medical_platform"))

    jwt_secret: str = field(default_factory=lambda: _get("JWT_SECRET", "dev-secret-change-me-please-32bytes-min"))
    jwt_expire_hours: int = int(_get("JWT_EXPIRE_HOURS", "12"))

    project_dir: Path = Path(__file__).resolve().parents[1]
    samples_dir: Path = project_dir / "data" / "samples"
    outputs_dir: Path = project_dir / "outputs"

    @property
    def offline(self) -> bool:
        return not self.llm_api_key


settings = Settings()
