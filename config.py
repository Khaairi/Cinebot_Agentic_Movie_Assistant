"""
Configuration management for CineBot application.
Handles environment variables and application settings.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class APIConfig:
    """API configuration settings."""
    gemini_key: str
    tmdb_api_key: str
    google_api_key: str
    google_cse_id: str
    qdrant_url: str
    qdrant_api_key: str
    
    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        return cls(
            gemini_key=os.getenv("GEMINI_KEY", ""),
            tmdb_api_key=os.getenv("TMDB_API_KEY", ""),
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
            google_cse_id=os.getenv("GOOGLE_CSE_ID", ""),
            qdrant_url=os.getenv("QDRANT_URL", ""),
            qdrant_api_key=os.getenv("QDRANT_API_KEY", "")
        )


@dataclass
class AppConfig:
    """Application configuration settings."""
    page_title: str = "CineBot"
    page_icon: str = "🎬"
    layout: str = "centered"
    collection_name: str = "cinebot"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "gemini-2.5-flash"


# Global configuration instances
api_config = APIConfig.from_env()
app_config = AppConfig()