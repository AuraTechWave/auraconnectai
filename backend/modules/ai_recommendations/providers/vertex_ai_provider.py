# backend/modules/ai_recommendations/providers/vertex_ai_provider.py

import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
import logging
from google.cloud import aiplatform
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from vertexai.language_models import TextGenerationModel, TextEmbeddingModel

from ..interfaces.model_provider_interface import (
    ModelProviderInterface,
    ModelProviderConfig,
    ModelRequest,
    ModelResponse,
    ModelCapability,
    ModelProviderAuthError,
    ModelProviderRateLimitError,
    ModelProviderTimeoutError,
    ModelProviderInvalidRequestError
)

logger = logging.getLogger(__name__)


class VertexAIProvider(ModelProviderInterface):
    """
    Google Cloud Vertex AI provider implementation.
    
    Supports PaLM 2, Gemini, and other Vertex AI models.
    """
    
    def __init__(self, config: ModelProviderConfig):
        self.config = config
        
        # Extract GCP configuration
        self.project_id = config.extra_config.get("project_id")
        self.location = config.extra_config.get("location", "us-central1")
        self.credentials_path = config.extra_config.get("credentials_path")
        
        if not self.project_id:
            raise ValueError("project_id must be provided in extra_config")
        
        # Initialize Vertex AI
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                aiplatform.init(
                    project=self.project_id,
                    location=self.location,
                    credentials=credentials
                )
            else:
                # Use default credentials
                aiplatform.init(
                    project=self.project_id,
                    location=self.location
                )
            
            vertexai.init(project=self.project_id, location=self.location)
            
        except Exception as e:
            raise ModelProviderAuthError(f"Failed to initialize Vertex AI: {e}")
        
        self.default_model = config.default_model or "text-bison"
        
        # Model type mapping
        self.model_types = {
            "text-bison": "palm2",
            "text-unicorn": "palm2",
            "gemini-pro": "gemini",
            "gemini-pro-vision": "gemini",
            "textembedding-gecko": "embedding"
        }
    
    @property
    def name(self) -> str:
        return "vertex_ai"
    
    @property
    def capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CHAT,
            ModelCapability.EMBEDDINGS,
            ModelCapability.CODE_GENERATION,
            ModelCapability.QUESTION_ANSWERING,
            ModelCapability.SUMMARIZATION
        ]
    
    def _get_model_type(self, model_name: str) -> str:
        """Determine model type from model name"""
        for prefix, model_type in self.model_types.items():
            if model_name.startswith(prefix):
                return model_type
        return "palm2"  # Default
    
    async def generate(
        self,
        request: ModelRequest,
        model: Optional[str] = None
    ) -> ModelResponse:
        """Generate a response from Vertex AI"""
        start_time = datetime.utcnow()
        model_name = model or self.default_model
        model_type = self._get_model_type(model_name)
        
        try:
            if model_type == "gemini":
                # Use Gemini models
                response_text = await self._generate_gemini(request, model_name)
            else:
                # Use PaLM 2 models
                response_text = await self._generate_palm(request, model_name)
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return ModelResponse(
                text=response_text,
                model_name=model_name,
                provider_name=self.name,
                response_time_ms=response_time,
                confidence_score=None,
                provider_metadata={
                    "project_id": self.project_id,
                    "location": self.location,
                    "model_type": model_type
                },
                request_id=request.request_id
            )
            
        except Exception as e:
            if "quota" in str(e).lower():
                raise ModelProviderRateLimitError(f"Quota exceeded: {e}")
            elif "timeout" in str(e).lower():
                raise ModelProviderTimeoutError(f"Request timeout: {e}")
            elif "permission" in str(e).lower() or "auth" in str(e).lower():
                raise ModelProviderAuthError(f"Authentication error: {e}")
            else:
                raise ModelProviderInvalidRequestError(f"Request failed: {e}")
    
    async def _generate_palm(
        self,
        request: ModelRequest,
        model_name: str
    ) -> str:
        """Generate using PaLM 2 models"""
        model = TextGenerationModel.from_pretrained(model_name)
        
        parameters = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
            "top_p": request.top_p,
            **request.provider_params
        }
        
        if request.stop_sequences:
            parameters["stop_sequences"] = request.stop_sequences
        
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.predict(request.prompt, **parameters)
        )
        
        return response.text
    
    async def _generate_gemini(
        self,
        request: ModelRequest,
        model_name: str
    ) -> str:
        """Generate using Gemini models"""
        model = GenerativeModel(model_name)
        
        generation_config = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
            "top_p": request.top_p,
            **request.provider_params
        }
        
        if request.stop_sequences:
            generation_config["stop_sequences"] = request.stop_sequences
        
        # Handle chat messages if provided
        if request.messages:
            # Convert to Gemini chat format
            chat = model.start_chat()
            for message in request.messages[:-1]:  # All but last message
                if message["role"] == "user":
                    chat.send_message(message["content"])
                # Gemini handles assistant messages internally
            
            # Send last user message and get response
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(
                    request.messages[-1]["content"],
                    generation_config=generation_config
                )
            )
        else:
            # Single prompt
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    request.prompt,
                    generation_config=generation_config
                )
            )
        
        return response.text
    
    async def generate_stream(
        self,
        request: ModelRequest,
        model: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Generate streaming response"""
        model_name = model or self.default_model
        model_type = self._get_model_type(model_name)
        
        if model_type == "gemini":
            # Gemini supports streaming
            model = GenerativeModel(model_name)
            
            generation_config = {
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
                "top_p": request.top_p
            }
            
            loop = asyncio.get_event_loop()
            response_stream = await loop.run_in_executor(
                None,
                lambda: model.generate_content(
                    request.prompt,
                    generation_config=generation_config,
                    stream=True
                )
            )
            
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        else:
            # PaLM doesn't support streaming - simulate it
            response = await self.generate(request, model)
            words = response.text.split()
            for i, word in enumerate(words):
                if i > 0:
                    yield " "
                yield word
                await asyncio.sleep(0.01)
    
    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Create embeddings using Vertex AI"""
        model_name = model or "textembedding-gecko"
        
        model = TextEmbeddingModel.from_pretrained(model_name)
        
        embeddings = []
        
        # Process in batches (Vertex AI has batch limits)
        batch_size = 5
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            batch_embeddings = await loop.run_in_executor(
                None,
                lambda: model.get_embeddings(batch)
            )
            
            for embedding in batch_embeddings:
                embeddings.append(embedding.values)
        
        return embeddings
    
    async def validate_connection(self) -> bool:
        """Validate Vertex AI connection"""
        try:
            # Try to list available models
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(
                None,
                lambda: aiplatform.Model.list()
            )
            return True
        except Exception as e:
            logger.error(f"Vertex AI connection validation error: {e}")
            return False
    
    async def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get model information"""
        model_type = self._get_model_type(model)
        
        info = {
            "id": model,
            "provider": self.name,
            "type": model_type,
            "project_id": self.project_id,
            "location": self.location
        }
        
        # Add model-specific information
        if model.startswith("text-bison"):
            info.update({
                "max_tokens": 1024,
                "training_cutoff": "April 2023",
                "capabilities": ["text_generation", "summarization", "question_answering"]
            })
        elif model.startswith("gemini-pro"):
            info.update({
                "max_tokens": 2048,
                "capabilities": ["text_generation", "chat", "code_generation"],
                "supports_streaming": True,
                "supports_vision": "vision" in model
            })
        elif model.startswith("textembedding-gecko"):
            info.update({
                "embedding_dimension": 768,
                "max_input_tokens": 3072,
                "capabilities": ["embeddings"]
            })
        
        return info
    
    async def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens for Vertex AI models"""
        # Vertex AI doesn't provide a direct token counting API
        # Use rough estimation based on model type
        model_name = model or self.default_model
        
        if model_name.startswith("gemini"):
            # Gemini uses similar tokenization to GPT models
            # Rough estimate: ~4 characters per token
            return len(text) // 4
        else:
            # PaLM models use different tokenization
            # Rough estimate: ~3 characters per token
            return len(text) // 3
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check with quota information"""
        health_info = await super().health_check()
        
        if health_info["status"] == "healthy":
            try:
                # Check quotas if possible
                health_info["details"]["project_id"] = self.project_id
                health_info["details"]["location"] = self.location
                health_info["details"]["models_available"] = list(self.model_types.keys())
            except Exception as e:
                health_info["details"]["quota_check_error"] = str(e)
        
        return health_info