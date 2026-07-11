import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
import dotenv

# Load environment variables from .env file into os.environ
backend_dir = Path(__file__).resolve().parent.parent.parent
dotenv.load_dotenv(dotenv_path=backend_dir / ".env")

# Ensure GOOGLE_APPLICATION_CREDENTIALS is an absolute path so Google Cloud SDK resolves it properly
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    sa_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    if not os.path.isabs(sa_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((backend_dir / sa_path).resolve())



class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = Field(default="UnifyOps", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000", alias="CORS_ORIGINS"
    )

    # Firebase
    firebase_service_account_key_path: str = Field(
        default="", alias="FIREBASE_SERVICE_ACCOUNT_KEY_PATH"
    )

    # ─── GCP Services ───
    gcp_project_id: str = Field(default="unifyops", alias="GCP_PROJECT_ID")
    gcp_location: str = Field(default="us", alias="GCP_LOCATION")

    # Cloud Storage
    gcs_bucket_name: str = Field(
        default="unifyops-documents-bucket", alias="GCS_BUCKET_NAME"
    )

    # Document AI Processor IDs
    docai_ocr_processor_id: str = Field(
        default="", alias="DOCAI_OCR_PROCESSOR_ID"
    )
    docai_classifier_processor_id: str = Field(
        default="", alias="DOCAI_CLASSIFIER_PROCESSOR_ID"
    )
    docai_pid_extractor_processor_id: str = Field(
        default="", alias="DOCAI_PID_EXTRACTOR_PROCESSOR_ID"
    )

    # Gemini (Google AI Studio)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # Groq (Fallback LLM provider)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    # Confidence thresholds
    classification_confidence_threshold: float = Field(
        default=0.80, alias="CLASSIFICATION_CONFIDENCE_THRESHOLD"
    )
    entity_confidence_threshold: float = Field(
        default=0.85, alias="ENTITY_CONFIDENCE_THRESHOLD"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def docai_ocr_processor_path(self) -> str:
        return (
            f"projects/{self.gcp_project_id}/locations/{self.gcp_location}"
            f"/processors/{self.docai_ocr_processor_id}"
        )

    @property
    def docai_classifier_processor_path(self) -> str:
        return (
            f"projects/{self.gcp_project_id}/locations/{self.gcp_location}"
            f"/processors/{self.docai_classifier_processor_id}"
        )

    @property
    def docai_pid_extractor_processor_path(self) -> str:
        return (
            f"projects/{self.gcp_project_id}/locations/{self.gcp_location}"
            f"/processors/{self.docai_pid_extractor_processor_id}"
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }


settings = Settings()
