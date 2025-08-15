# backend/modules/ai_recommendations/interfaces/model_provider_interface.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, AsyncIterator
from datetime import datetime
from pydantic import BaseModel, Field
import asyncio
from enum import Enum


class ModelCapability(str, Enum):
    """Capabilities that a model provider can support"""

    TEXT_GENERATION = "text_generation"
    TEXT_COMPLETION = "text_completion"
    CHAT = "chat"
    EMBEDDINGS = "embeddings"
    CLASSIFICATION = "classification"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    QUESTION_ANSWERING = "question_answering"
    CODE_GENERATION = "code_generation"
    IMAGE_GENERATION = "image_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


class ModelRequest(BaseModel):
    """Standard request format for all model providers"""

    prompt: Optional[str] = Field(None, description="Main input text")
    messages: Optional[List[Dict[str, str]]] = Field(
        None, description="Chat messages for conversational models"
    )

    max_tokens: Optional[int] = Field(256, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(
        0.7, ge=0, le=2, description="Sampling temperature"
    )
    top_p: Optional[float] = Field(1.0, ge=0, le=1, description="Top-p sampling")

    stop_sequences: Optional[List[str]] = Field(None, description="Stop sequences")

    # Provider-specific parameters
    provider_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Provider-specific parameters"
    )

    # Context and metadata
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional context for the request"
    )

    user_id: Optional[int] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None


class ModelResponse(BaseModel):
    """Standard response format from all model providers"""

    # Main response content
    text: Optional[str] = Field(None, description="Generated text response")
    embeddings: Optional[List[float]] = Field(None, description="Embedding vector")

    # Multiple choices for sampling
    choices: Optional[List[Dict[str, Any]]] = Field(
        None, description="Multiple response choices"
    )

    # Metadata
    model_name: str
    provider_name: str

    # Performance metrics
    completion_tokens: Optional[int] = None
    prompt_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    response_time_ms: float
    confidence_score: Optional[float] = Field(None, ge=0, le=1)

    # Provider-specific data
    provider_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Provider-specific response metadata"
    )

    # Request tracking
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ModelProviderConfig(BaseModel):
    """Configuration for a model provider"""

    provider_name: str
    api_key: Optional[str] = Field(None, description="API key for authentication")
    api_base_url: Optional[str] = Field(None, description="Base URL for API calls")

    # Model settings
    default_model: str
    available_models: List[str] = Field(default_factory=list)

    # Rate limiting
    max_requests_per_minute: Optional[int] = None
    max_tokens_per_minute: Optional[int] = None

    # Timeouts and retries
    timeout_seconds: float = Field(30.0, gt=0)
    max_retries: int = Field(3, ge=0)
    retry_delay_seconds: float = Field(1.0, gt=0)

    # Feature flags
    supports_streaming: bool = False
    supports_function_calling: bool = False
    supports_vision: bool = False

    # Custom headers or auth
    custom_headers: Optional[Dict[str, str]] = Field(default_factory=dict)

    # Provider-specific config
    extra_config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ModelProviderInterface(ABC):
    """
    Abstract interface for pluggable AI model providers.

    This interface allows seamless integration of different model providers
    like OpenAI, Anthropic, HuggingFace, Google Vertex AI, AWS Bedrock, etc.
    """

    @abstractmethod
    def __init__(self, config: ModelProviderConfig):
        """Initialize the provider with configuration"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name"""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[ModelCapability]:
        """Return list of supported capabilities"""
        pass

    @abstractmethod
    async def generate(
        self, request: ModelRequest, model: Optional[str] = None
    ) -> ModelResponse:
        """
        Generate a response from the model.

        Args:
            request: Standard model request
            model: Optional model override (uses default if not specified)

        Returns:
            ModelResponse with generated content
        """
        pass

    @abstractmethod
    async def generate_stream(
        self, request: ModelRequest, model: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response from the model.

        Args:
            request: Standard model request
            model: Optional model override

        Yields:
            String chunks of the response
        """
        pass

    @abstractmethod
    async def create_embeddings(
        self, texts: List[str], model: Optional[str] = None
    ) -> List[List[float]]:
        """
        Create embeddings for the given texts.

        Args:
            texts: List of texts to embed
            model: Optional embedding model override

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate that the provider is properly configured and accessible.

        Returns:
            True if connection is valid, False otherwise
        """
        pass

    @abstractmethod
    async def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get information about a specific model.

        Args:
            model: Model identifier

        Returns:
            Dictionary with model information (context length, capabilities, etc.)
        """
        pass

    # Optional methods with default implementations

    async def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """
        Count tokens in the text for the specified model.

        Default implementation provides rough estimate.
        """
        # Rough estimate: ~4 characters per token
        return len(text) // 4

    async def moderate_content(
        self, text: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check content for safety/moderation issues.

        Returns dict with safety scores and flags.
        """
        return {"safe": True, "categories": {}, "scores": {}}

    def get_rate_limiter(self) -> Optional[Any]:
        """
        Get rate limiter instance if implemented.
        """
        return None

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the provider.

        Returns status and diagnostic information.
        """
        try:
            is_valid = await self.validate_connection()
            return {
                "status": "healthy" if is_valid else "unhealthy",
                "provider": self.name,
                "timestamp": datetime.utcnow().isoformat(),
                "details": {},
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.name,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
            }


class ModelProviderException(Exception):
    """Base exception for model provider errors"""

    pass


class ModelProviderAuthError(ModelProviderException):
    """Authentication error with model provider"""

    pass


class ModelProviderRateLimitError(ModelProviderException):
    """Rate limit exceeded error"""

    pass


class ModelProviderTimeoutError(ModelProviderException):
    """Request timeout error"""

    pass


class ModelProviderInvalidRequestError(ModelProviderException):
    """Invalid request parameters error"""

    pass
