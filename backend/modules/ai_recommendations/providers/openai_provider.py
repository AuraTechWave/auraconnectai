# backend/modules/ai_recommendations/providers/openai_provider.py

import aiohttp
import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
import logging
import backoff

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


class OpenAIProvider(ModelProviderInterface):
    """
    OpenAI model provider implementation.
    
    Supports GPT-3.5, GPT-4, and embedding models.
    """
    
    def __init__(self, config: ModelProviderConfig):
        self.config = config
        self.api_key = config.api_key
        self.api_base = config.api_base_url or "https://api.openai.com/v1"
        self.default_model = config.default_model or "gpt-3.5-turbo"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **config.custom_headers
        }
        
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.TEXT_GENERATION,
            ModelCapability.CHAT,
            ModelCapability.EMBEDDINGS,
            ModelCapability.CODE_GENERATION,
            ModelCapability.QUESTION_ANSWERING
        ]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout
            )
        return self._session
    
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        stream: bool = False
    ) -> Any:
        """Make API request with retry logic"""
        session = await self._get_session()
        url = f"{self.api_base}/{endpoint}"
        
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 401:
                    raise ModelProviderAuthError("Invalid API key")
                elif response.status == 429:
                    raise ModelProviderRateLimitError("Rate limit exceeded")
                elif response.status >= 400:
                    error_data = await response.json()
                    raise ModelProviderInvalidRequestError(
                        f"API error: {error_data.get('error', {}).get('message', 'Unknown error')}"
                    )
                
                if stream:
                    return response
                else:
                    return await response.json()
                    
        except asyncio.TimeoutError:
            raise ModelProviderTimeoutError(f"Request timeout after {self.config.timeout_seconds}s")
    
    async def generate(
        self,
        request: ModelRequest,
        model: Optional[str] = None
    ) -> ModelResponse:
        """Generate a response from OpenAI"""
        start_time = datetime.utcnow()
        model_name = model or self.default_model
        
        # Build payload
        payload = {
            "model": model_name,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            **request.provider_params
        }
        
        # Handle chat vs completion models
        if model_name.startswith("gpt-"):
            # Chat model
            if request.messages:
                payload["messages"] = request.messages
            else:
                payload["messages"] = [{"role": "user", "content": request.prompt}]
            endpoint = "chat/completions"
        else:
            # Legacy completion model
            payload["prompt"] = request.prompt
            endpoint = "completions"
        
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
        
        # Make request
        response_data = await self._make_request(endpoint, payload)
        
        # Parse response
        if endpoint == "chat/completions":
            text = response_data["choices"][0]["message"]["content"]
        else:
            text = response_data["choices"][0]["text"]
        
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ModelResponse(
            text=text,
            model_name=model_name,
            provider_name=self.name,
            completion_tokens=response_data["usage"].get("completion_tokens"),
            prompt_tokens=response_data["usage"].get("prompt_tokens"),
            total_tokens=response_data["usage"].get("total_tokens"),
            response_time_ms=response_time,
            confidence_score=None,  # OpenAI doesn't provide confidence
            provider_metadata={
                "id": response_data.get("id"),
                "object": response_data.get("object"),
                "created": response_data.get("created"),
                "finish_reason": response_data["choices"][0].get("finish_reason")
            },
            request_id=request.request_id
        )
    
    async def generate_stream(
        self,
        request: ModelRequest,
        model: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Generate a streaming response from OpenAI"""
        model_name = model or self.default_model
        
        payload = {
            "model": model_name,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "stream": True,
            **request.provider_params
        }
        
        if model_name.startswith("gpt-"):
            if request.messages:
                payload["messages"] = request.messages
            else:
                payload["messages"] = [{"role": "user", "content": request.prompt}]
            endpoint = "chat/completions"
        else:
            payload["prompt"] = request.prompt
            endpoint = "completions"
        
        session = await self._get_session()
        url = f"{self.api_base}/{endpoint}"
        
        async with session.post(url, json=payload) as response:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if endpoint == "chat/completions":
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        else:
                            text = data["choices"][0].get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
    
    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Create embeddings using OpenAI"""
        model_name = model or "text-embedding-ada-002"
        
        payload = {
            "model": model_name,
            "input": texts
        }
        
        response_data = await self._make_request("embeddings", payload)
        
        embeddings = []
        for item in sorted(response_data["data"], key=lambda x: x["index"]):
            embeddings.append(item["embedding"])
        
        return embeddings
    
    async def validate_connection(self) -> bool:
        """Validate OpenAI connection"""
        try:
            # Try to list models
            session = await self._get_session()
            url = f"{self.api_base}/models"
            
            async with session.get(url) as response:
                if response.status == 200:
                    return True
                elif response.status == 401:
                    logger.error("Invalid OpenAI API key")
                    return False
                else:
                    logger.error(f"OpenAI connection validation failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"OpenAI connection validation error: {e}")
            return False
    
    async def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get information about a specific model"""
        session = await self._get_session()
        url = f"{self.api_base}/models/{model}"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "id": data.get("id"),
                        "object": data.get("object"),
                        "created": data.get("created"),
                        "owned_by": data.get("owned_by"),
                        "permission": data.get("permission", []),
                        "root": data.get("root"),
                        "parent": data.get("parent")
                    }
                else:
                    return {"error": f"Model not found: {model}"}
                    
        except Exception as e:
            return {"error": str(e)}
    
    async def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens using tiktoken if available"""
        try:
            import tiktoken
            model_name = model or self.default_model
            
            # Get encoding for model
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except KeyError:
                # Fall back to cl100k_base for newer models
                encoding = tiktoken.get_encoding("cl100k_base")
            
            return len(encoding.encode(text))
            
        except ImportError:
            # Fall back to rough estimate
            return await super().count_tokens(text, model)
    
    async def moderate_content(
        self,
        text: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use OpenAI moderation API"""
        payload = {"input": text}
        
        try:
            response_data = await self._make_request("moderations", payload)
            
            results = response_data["results"][0]
            categories = results["categories"]
            scores = results["category_scores"]
            
            # Check if any category is flagged
            is_safe = not any(categories.values())
            
            return {
                "safe": is_safe,
                "categories": categories,
                "scores": scores,
                "flagged": results.get("flagged", not is_safe)
            }
            
        except Exception as e:
            logger.error(f"Moderation error: {e}")
            # Fall back to default implementation
            return await super().moderate_content(text, model)
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup session"""
        if self._session and not self._session.closed:
            await self._session.close()