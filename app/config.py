"""
PULSE - Configuration Module
Loads environment variables and provides typed configuration.
Uses Azure RBAC (DefaultAzureCredential) for all Azure service authentication.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AzureOpenAIConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", ""))
    api_version: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"))
    deployment_name: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"))
    model_name: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_MODEL_NAME", "gpt-4o"))
    embedding_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"))
    embedding_model: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"))
    image_endpoint: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_IMAGE_ENDPOINT", ""))
    image_deployment: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT", "gpt-image-1"))


@dataclass
class AzureSearchConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_ENDPOINT", ""))
    index_name: str = field(default_factory=lambda: os.getenv("AZURE_SEARCH_INDEX_NAME", "pulse-knowledge-base"))


@dataclass
class LangSmithConfig:
    tracing_enabled: bool = field(default_factory=lambda: os.getenv("LANGCHAIN_TRACING_V2", "true").lower() == "true")
    api_key: str = field(default_factory=lambda: os.getenv("LANGCHAIN_API_KEY", ""))
    project: str = field(default_factory=lambda: os.getenv("LANGCHAIN_PROJECT", "pulse-newsroom-orchestrator"))
    endpoint: str = field(default_factory=lambda: os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"))


@dataclass
class AgentConfig:
    max_iterations: int = field(default_factory=lambda: int(os.getenv("AGENT_MAX_ITERATIONS", "10")))
    temperature: float = field(default_factory=lambda: float(os.getenv("AGENT_TEMPERATURE", "0.3")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("AGENT_MAX_TOKENS", "4096")))


@dataclass
class AzureSpeechConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("AZURE_SPEECH_ENDPOINT", ""))
    region: str = field(default_factory=lambda: os.getenv("AZURE_SPEECH_REGION", os.getenv("SPEECH_REGION", "eastus")))
    resource_url: str = field(default_factory=lambda: os.getenv("SPEECH_RESOURCE_URL", ""))


@dataclass
class AzureAvatarSpeechConfig:
    """Separate Speech resource for Avatar (must be in an Avatar-supported region)."""
    endpoint: str = field(default_factory=lambda: os.getenv("AZURE_AVATAR_SPEECH_ENDPOINT", ""))
    region: str = field(default_factory=lambda: os.getenv("AZURE_AVATAR_SPEECH_REGION", ""))


@dataclass
class AzureVideoIndexerConfig:
    account_id: str = field(default_factory=lambda: os.getenv("AZURE_VIDEO_INDEXER_ACCOUNT_ID", ""))
    location: str = field(default_factory=lambda: os.getenv("AZURE_VIDEO_INDEXER_LOCATION", "eastus"))
    resource_id: str = field(default_factory=lambda: os.getenv("AZURE_VIDEO_INDEXER_RESOURCE_ID", ""))


@dataclass
class AzureMapsConfig:
    subscription_key: str = field(default_factory=lambda: os.getenv("AZURE_MAPS_SUBSCRIPTION_KEY", ""))
    client_id: str = field(default_factory=lambda: os.getenv("AZURE_MAPS_CLIENT_ID", ""))


@dataclass
class AzureContentSafetyConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT", ""))


@dataclass
class AzureAvatarConfig:
    stt_locales: str = field(default_factory=lambda: os.getenv("STT_LOCALES", "en-US"))
    tts_voice: str = field(default_factory=lambda: os.getenv("TTS_VOICE", "en-US-AvaMultilingualNeural"))
    custom_voice_endpoint_id: str = field(default_factory=lambda: os.getenv("CUSTOM_VOICE_ENDPOINT_ID", ""))
    personal_voice_speaker_profile_id: str = field(default_factory=lambda: os.getenv("PERSONAL_VOICE_SPEAKER_PROFILE_ID", ""))
    continuous_conversation: bool = field(default_factory=lambda: os.getenv("CONTINUOUS_CONVERSATION", "true").lower() == "true")
    avatar_character: str = field(default_factory=lambda: os.getenv("AVATAR_CHARACTER", "meg"))
    avatar_style: str = field(default_factory=lambda: os.getenv("AVATAR_STYLE", "formal"))
    custom_avatar: bool = field(default_factory=lambda: os.getenv("CUSTOM_AVATAR", "false").lower() == "true")
    auto_reconnect: bool = field(default_factory=lambda: os.getenv("AUTO_RECONNECT", "false").lower() == "true")
    use_local_video_for_idle: bool = field(default_factory=lambda: os.getenv("USE_LOCAL_VIDEO_FOR_IDLE", "false").lower() == "true")
    transparent_background: bool = field(default_factory=lambda: os.getenv("TRANSPARENT_BACKGROUND", "true").lower() == "true")
    enable_oyd: bool = field(default_factory=lambda: os.getenv("ENABLE_OYD", "false").lower() == "true")


@dataclass
class AppConfig:
    name: str = field(default_factory=lambda: os.getenv("APP_NAME", "PULSE"))
    version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))
    host: str = field(default_factory=lambda: os.getenv("APP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("APP_DEBUG", "true").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    demo_mode: bool = field(default_factory=lambda: os.getenv("DEMO_MODE", "true").lower() == "true")

    azure_openai: AzureOpenAIConfig = field(default_factory=AzureOpenAIConfig)
    azure_search: AzureSearchConfig = field(default_factory=AzureSearchConfig)
    azure_speech: AzureSpeechConfig = field(default_factory=AzureSpeechConfig)
    azure_avatar_speech: AzureAvatarSpeechConfig = field(default_factory=AzureAvatarSpeechConfig)
    azure_video: AzureVideoIndexerConfig = field(default_factory=AzureVideoIndexerConfig)
    azure_maps: AzureMapsConfig = field(default_factory=AzureMapsConfig)
    azure_content_safety: AzureContentSafetyConfig = field(default_factory=AzureContentSafetyConfig)
    azure_avatar: AzureAvatarConfig = field(default_factory=AzureAvatarConfig)
    langsmith: LangSmithConfig = field(default_factory=LangSmithConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


# Singleton configuration instance
settings = AppConfig()
