# backend/modules/ai_recommendations/providers/huggingface_provider.py

import aiohttp
import asyncio
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
import logging
import json

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


class HuggingFaceProvider(ModelProviderInterface):
    """
    HuggingFace Inference API provider implementation.
    
    Supports both Inference API and Inference Endpoints.
    """
    
    def __init__(self, config: ModelProviderConfig):
        self.config = config
        self.api_key = config.api_key
        self.api_base = config.api_base_url or "https://api-inference.huggingface.co/models"
        self.default_model = config.default_model
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **config.custom_headers
        }
        
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Map model types to capabilities
        self.model_capabilities = {
            "text-generation": ModelCapability.TEXT_GENERATION,
            "text2text-generation": ModelCapability.TEXT_GENERATION,
            "summarization": ModelCapability.SUMMARIZATION,
            "translation": ModelCapability.TRANSLATION,
            "text-classification": ModelCapability.CLASSIFICATION,
            "sentiment-analysis": ModelCapability.SENTIMENT_ANALYSIS,
            "question-answering": ModelCapability.QUESTION_ANSWERING,
            "feature-extraction": ModelCapability.EMBEDDINGS
        }
    
    @property
    def name(self) -> str:
        return "huggingface"
    
    @property
    def capabilities(self) -> List[ModelCapability]:
        # Return all possible capabilities - actual support depends on model
        return list(set(self.model_capabilities.values()))
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout
            )
        return self._session
    
    async def _make_request(
        self,
        model: str,
        payload: Dict[str, Any],
        stream: bool = False
    ) -> Any:
        """Make API request to HuggingFace"""
        session = await self._get_session()
        
        # Handle custom endpoints
        if model.startswith("https://"):
            url = model
        else:
            url = f"{self.api_base}/{model}"
        
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 401:
                    raise ModelProviderAuthError("Invalid API token")
                elif response.status == 429:
                    raise ModelProviderRateLimitError("Rate limit exceeded")
                elif response.status == 503:
                    # Model is loading
                    error_data = await response.json()
                    estimated_time = error_data.get("estimated_time", 20)
                    raise ModelProviderTimeoutError(
                        f"Model is loading. Estimated time: {estimated_time}s"
                    )
                elif response.status >= 400:
                    error_data = await response.json()
                    raise ModelProviderInvalidRequestError(
                        f"API error: {error_data.get('error', 'Unknown error')}"
                    )
                
                if stream:
                    # HuggingFace Inference API doesn't support streaming natively
                    # Return the response for manual handling
                    return await response.json()
                else:
                    return await response.json()
                    
        except asyncio.TimeoutError:
            raise ModelProviderTimeoutError(f"Request timeout after {self.config.timeout_seconds}s")
    
    async def generate(
        self,
        request: ModelRequest,
        model: Optional[str] = None
    ) -> ModelResponse:
        """Generate a response from HuggingFace"""
        start_time = datetime.utcnow()
        model_name = model or self.default_model
        
        # Build payload based on model type
        if "gpt" in model_name.lower() or "bloom" in model_name.lower():
            # Text generation models
            payload = {
                "inputs": request.prompt,
                "parameters": {
                    "max_new_tokens": request.max_tokens,
                    "temperature": request.temperature,
                    "top_p": request.top_p,
                    "return_full_text": False,
                    **request.provider_params
                }
            }
        else:
            # Generic payload
            payload = {
                "inputs": request.prompt,
                "parameters": request.provider_params
            }
        
        if request.stop_sequences:
            payload["parameters"]["stop_sequences"] = request.stop_sequences
        
        # Make request
        response_data = await self._make_request(model_name, payload)
        
        # Parse response based on model output format
        if isinstance(response_data, list) and len(response_data) > 0:
            # Text generation response
            if isinstance(response_data[0], dict):
                text = response_data[0].get("generated_text", "")
            else:
                text = str(response_data[0])
        elif isinstance(response_data, dict):
            # Some models return dict directly
            text = response_data.get("generated_text", response_data.get("translation_text", ""))
        else:
            text = str(response_data)
        
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ModelResponse(
            text=text,
            model_name=model_name,
            provider_name=self.name,
            response_time_ms=response_time,
            confidence_score=None,
            provider_metadata={
                "raw_response": response_data
            },
            request_id=request.request_id
        )
    
    async def generate_stream(
        self,
        request: ModelRequest,
        model: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Generate streaming response (simulated for HuggingFace)"""
        # HuggingFace Inference API doesn't support true streaming
        # We'll generate the full response and yield it in chunks
        response = await self.generate(request, model)
        
        # Simulate streaming by yielding words
        words = response.text.split()
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word
            await asyncio.sleep(0.01)  # Small delay to simulate streaming
    
    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Create embeddings using HuggingFace"""
        model_name = model or "sentence-transformers/all-MiniLM-L6-v2"
        
        embeddings = []
        
        # HuggingFace expects single text input for feature extraction
        for text in texts:
            payload = {"inputs": text}
            
            response_data = await self._make_request(model_name, payload)
            
            # Extract embeddings from response
            if isinstance(response_data, list) and len(response_data) > 0:
                # Feature extraction returns nested list
                if isinstance(response_data[0], list) and len(response_data[0]) > 0:
                    # Take mean of token embeddings for sentence embedding
                    embedding = [sum(col) / len(col) for col in zip(*response_data[0])]
                else:
                    embedding = response_data[0]
            else:
                raise ModelProviderInvalidRequestError("Invalid embedding response format")
            
            embeddings.append(embedding)
        
        return embeddings
    
    async def validate_connection(self) -> bool:
        """Validate HuggingFace connection"""
        try:
            # Try a simple request with a small model
            test_payload = {
                "inputs": "Hello",
                "parameters": {"max_new_tokens": 1}
            }
            
            await self._make_request("gpt2", test_payload)
            return True
            
        except ModelProviderAuthError:
            logger.error("Invalid HuggingFace API token")
            return False
        except Exception as e:
            logger.error(f"HuggingFace connection validation error: {e}")
            return False
    
    async def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get model information from HuggingFace"""
        session = await self._get_session()
        
        # Use HuggingFace Hub API
        hub_url = f"https://huggingface.co/api/models/{model}"
        
        try:
            async with session.get(hub_url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "id": data.get("id"),
                        "pipeline_tag": data.get("pipeline_tag"),
                        "task": data.get("task"),
                        "library_name": data.get("library_name"),
                        "language": data.get("language"),
                        "tags": data.get("tags", []),
                        "downloads": data.get("downloads"),
                        "likes": data.get("likes")
                    }
                else:
                    return {"error": f"Model not found: {model}"}
                    
        except Exception as e:
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check with model loading status"""
        health_info = await super().health_check()
        
        # Check if default model is loaded
        if health_info["status"] == "healthy":
            try:
                test_payload = {
                    "inputs": "test",
                    "parameters": {"max_new_tokens": 1}
                }
                await self._make_request(self.default_model, test_payload)
                health_info["details"]["model_loaded"] = True
            except ModelProviderTimeoutError as e:
                health_info["details"]["model_loaded"] = False
                health_info["details"]["loading_message"] = str(e)
        
        return health_info
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup session"""
        if self._session and not self._session.closed:
            await self._session.close()