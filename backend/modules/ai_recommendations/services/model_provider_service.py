# backend/modules/ai_recommendations/services/model_provider_service.py

from typing import Dict, Any, List, Optional, Type
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from ..interfaces.model_provider_interface import (
    ModelProviderInterface,
    ModelProviderConfig,
    ModelRequest,
    ModelResponse,
    ModelCapability,
    ModelProviderException
)
from ..providers.openai_provider import OpenAIProvider
from ..providers.huggingface_provider import HuggingFaceProvider
from ..providers.vertex_ai_provider import VertexAIProvider
from ..metrics.model_metrics import ai_model_metrics

logger = logging.getLogger(__name__)


class ModelProviderRegistry:
    """Registry for available model providers"""
    
    def __init__(self):
        self._providers: Dict[str, Type[ModelProviderInterface]] = {
            "openai": OpenAIProvider,
            "huggingface": HuggingFaceProvider,
            "vertex_ai": VertexAIProvider,
        }
        
        self._instances: Dict[str, ModelProviderInterface] = {}
        self._configs: Dict[str, ModelProviderConfig] = {}
    
    def register_provider(
        self,
        name: str,
        provider_class: Type[ModelProviderInterface]
    ):
        """Register a new provider type"""
        self._providers[name] = provider_class
        logger.info(f"Registered model provider: {name}")
    
    def configure_provider(
        self,
        name: str,
        config: ModelProviderConfig
    ):
        """Configure a provider instance"""
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        
        self._configs[name] = config
        
        # Clear existing instance to force recreation with new config
        if name in self._instances:
            del self._instances[name]
        
        logger.info(f"Configured model provider: {name}")
    
    def get_provider(self, name: str) -> ModelProviderInterface:
        """Get a configured provider instance"""
        if name not in self._configs:
            raise ValueError(f"Provider not configured: {name}")
        
        if name not in self._instances:
            provider_class = self._providers[name]
            config = self._configs[name]
            self._instances[name] = provider_class(config)
        
        return self._instances[name]
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List available providers and their status"""
        providers = []
        
        for name, provider_class in self._providers.items():
            info = {
                "name": name,
                "class": provider_class.__name__,
                "configured": name in self._configs,
                "active": name in self._instances
            }
            
            if name in self._configs:
                config = self._configs[name]
                info["default_model"] = config.default_model
                info["supports_streaming"] = config.supports_streaming
            
            providers.append(info)
        
        return providers
    
    async def health_check_all(self) -> Dict[str, Any]:
        """Check health of all configured providers"""
        results = {}
        
        for name in self._configs:
            try:
                provider = self.get_provider(name)
                results[name] = await provider.health_check()
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results


class ModelProviderService:
    """
    Service for managing AI model providers and routing requests.
    
    Provides unified interface for multiple model providers with:
    - Provider selection and fallback
    - Request routing based on capabilities
    - Metrics and monitoring
    - Error handling and retries
    """
    
    def __init__(self):
        self.registry = ModelProviderRegistry()
        self._default_provider: Optional[str] = None
        self._fallback_providers: List[str] = []
    
    def configure_from_settings(self, settings: Dict[str, Any]):
        """Configure providers from application settings"""
        providers_config = settings.get("ai_providers", {})
        
        for provider_name, provider_settings in providers_config.items():
            if not provider_settings.get("enabled", True):
                continue
            
            config = ModelProviderConfig(
                provider_name=provider_name,
                api_key=provider_settings.get("api_key"),
                api_base_url=provider_settings.get("api_base_url"),
                default_model=provider_settings.get("default_model"),
                available_models=provider_settings.get("available_models", []),
                max_requests_per_minute=provider_settings.get("max_requests_per_minute"),
                max_tokens_per_minute=provider_settings.get("max_tokens_per_minute"),
                timeout_seconds=provider_settings.get("timeout_seconds", 30),
                max_retries=provider_settings.get("max_retries", 3),
                supports_streaming=provider_settings.get("supports_streaming", False),
                supports_function_calling=provider_settings.get("supports_function_calling", False),
                supports_vision=provider_settings.get("supports_vision", False),
                custom_headers=provider_settings.get("custom_headers", {}),
                extra_config=provider_settings.get("extra_config", {})
            )
            
            self.registry.configure_provider(provider_name, config)
        
        # Set default and fallback providers
        self._default_provider = settings.get("default_provider")
        self._fallback_providers = settings.get("fallback_providers", [])
        
        logger.info(
            f"Configured model providers. Default: {self._default_provider}, "
            f"Fallbacks: {self._fallback_providers}"
        )
    
    async def generate(
        self,
        request: ModelRequest,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        use_fallback: bool = True
    ) -> ModelResponse:
        """
        Generate a response using specified or default provider.
        
        Args:
            request: Model request
            provider_name: Specific provider to use
            model: Specific model to use
            use_fallback: Whether to try fallback providers on failure
            
        Returns:
            ModelResponse from the provider
        """
        providers_to_try = []
        
        if provider_name:
            providers_to_try.append(provider_name)
        elif self._default_provider:
            providers_to_try.append(self._default_provider)
        
        if use_fallback:
            providers_to_try.extend([
                p for p in self._fallback_providers 
                if p not in providers_to_try
            ])
        
        if not providers_to_try:
            raise ModelProviderException("No providers configured")
        
        last_error = None
        
        for provider_name in providers_to_try:
            try:
                provider = self.registry.get_provider(provider_name)
                
                # Track metrics
                request_id = request.request_id or str(datetime.utcnow().timestamp())
                domain = request.context.get("domain", "general")
                endpoint = request.context.get("endpoint", "generate")
                
                ai_model_metrics.track_request_start(
                    request_id,
                    provider_name,
                    domain,
                    endpoint
                )
                
                try:
                    response = await provider.generate(request, model)
                    
                    # Track success
                    ai_model_metrics.track_request_end(
                        request_id,
                        provider_name,
                        domain,
                        endpoint,
                        success=True,
                        confidence_score=response.confidence_score
                    )
                    
                    return response
                    
                except Exception as e:
                    # Track failure
                    ai_model_metrics.track_request_end(
                        request_id,
                        provider_name,
                        domain,
                        endpoint,
                        success=False,
                        error_type=type(e).__name__
                    )
                    raise
                    
            except Exception as e:
                logger.error(f"Provider {provider_name} failed: {e}")
                last_error = e
                
                if not use_fallback:
                    raise
                
                # Continue to next provider
                continue
        
        # All providers failed
        raise ModelProviderException(
            f"All providers failed. Last error: {last_error}"
        )
    
    async def generate_with_capability(
        self,
        request: ModelRequest,
        capability: ModelCapability,
        use_fallback: bool = True
    ) -> ModelResponse:
        """Generate response using a provider that supports the capability"""
        # Find providers that support the capability
        capable_providers = []
        
        for provider_info in self.registry.list_providers():
            if not provider_info["configured"]:
                continue
            
            provider = self.registry.get_provider(provider_info["name"])
            if capability in provider.capabilities:
                capable_providers.append(provider_info["name"])
        
        if not capable_providers:
            raise ModelProviderException(
                f"No configured providers support capability: {capability}"
            )
        
        # Try capable providers in order
        for provider_name in capable_providers:
            try:
                return await self.generate(
                    request,
                    provider_name=provider_name,
                    use_fallback=False
                )
            except Exception as e:
                if not use_fallback:
                    raise
                continue
        
        raise ModelProviderException(
            f"All capable providers failed for capability: {capability}"
        )
    
    @asynccontextmanager
    async def streaming_generate(
        self,
        request: ModelRequest,
        provider_name: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Context manager for streaming generation"""
        provider_name = provider_name or self._default_provider
        if not provider_name:
            raise ModelProviderException("No provider specified or configured")
        
        provider = self.registry.get_provider(provider_name)
        
        # Check if provider supports streaming
        config = self.registry._configs.get(provider_name)
        if not config or not config.supports_streaming:
            raise ModelProviderException(
                f"Provider {provider_name} does not support streaming"
            )
        
        # Track metrics
        request_id = request.request_id or str(datetime.utcnow().timestamp())
        domain = request.context.get("domain", "general")
        endpoint = request.context.get("endpoint", "generate_stream")
        
        ai_model_metrics.track_request_start(
            request_id,
            provider_name,
            domain,
            endpoint
        )
        
        try:
            stream = provider.generate_stream(request, model)
            yield stream
            
            # Track success
            ai_model_metrics.track_request_end(
                request_id,
                provider_name,
                domain,
                endpoint,
                success=True
            )
            
        except Exception as e:
            # Track failure
            ai_model_metrics.track_request_end(
                request_id,
                provider_name,
                domain,
                endpoint,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    async def create_embeddings(
        self,
        texts: List[str],
        provider_name: Optional[str] = None,
        model: Optional[str] = None
    ) -> List[List[float]]:
        """Create embeddings using specified provider"""
        # Find a provider that supports embeddings
        if not provider_name:
            for provider_info in self.registry.list_providers():
                if not provider_info["configured"]:
                    continue
                
                provider = self.registry.get_provider(provider_info["name"])
                if ModelCapability.EMBEDDINGS in provider.capabilities:
                    provider_name = provider_info["name"]
                    break
        
        if not provider_name:
            raise ModelProviderException("No provider configured for embeddings")
        
        provider = self.registry.get_provider(provider_name)
        return await provider.create_embeddings(texts, model)
    
    async def count_tokens(
        self,
        text: str,
        provider_name: Optional[str] = None,
        model: Optional[str] = None
    ) -> int:
        """Count tokens using specified provider"""
        provider_name = provider_name or self._default_provider
        if not provider_name:
            raise ModelProviderException("No provider specified or configured")
        
        provider = self.registry.get_provider(provider_name)
        return await provider.count_tokens(text, model)
    
    async def moderate_content(
        self,
        text: str,
        provider_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Moderate content using specified provider"""
        provider_name = provider_name or self._default_provider
        if not provider_name:
            raise ModelProviderException("No provider specified or configured")
        
        provider = self.registry.get_provider(provider_name)
        return await provider.moderate_content(text)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all providers"""
        return await self.registry.health_check_all()
    
    def get_provider_info(self) -> List[Dict[str, Any]]:
        """Get information about all providers"""
        return self.registry.list_providers()


# Create singleton service
model_provider_service = ModelProviderService()