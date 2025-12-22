"""
LLM Factory Module

Provides a unified interface for both Ollama and Groq API.
Allows seamless switching between local Ollama models and Groq API.
"""

import os
from typing import Optional, Protocol, runtime_checkable
from abc import ABC, abstractmethod

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# =============================================================================
# PROTOCOLS & INTERFACES
# =============================================================================

@runtime_checkable
class LLMInterface(Protocol):
    """Protocol defining the interface for LLM clients."""
    
    def invoke(self, prompt: str) -> str:
        """Invoke the LLM with a prompt and return the response."""
        ...


class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""
    
    def __init__(self, temperature: float = 0.7):
        self.temperature = temperature
    
    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Invoke the LLM with a prompt and return the response."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass


# =============================================================================
# OLLAMA IMPLEMENTATION
# =============================================================================

class OllamaLLM(BaseLLM):
    """Wrapper for Ollama LLM using langchain_ollama."""
    
    def __init__(
        self, 
        model_name: str = "llama3:latest", 
        temperature: float = 0.7,
        base_url: Optional[str] = None
    ):
        super().__init__(temperature)
        self._model_name = model_name
        self.host = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Import here to avoid circular imports and allow graceful degradation
        try:
            from langchain_ollama import OllamaLLM as LangchainOllama
            self._client = LangchainOllama(
                model=model_name, 
                temperature=temperature,
                host=self.host
            )
        except ImportError:
            raise ImportError(
                "langchain_ollama is required for Ollama support. "
                "Install with: pip install langchain-ollama"
            )
    
    def invoke(self, prompt: str) -> str:
        """Invoke Ollama with the given prompt."""
        return self._client.invoke(prompt)
    
    @property
    def model_name(self) -> str:
        return self._model_name


# =============================================================================
# GROQ IMPLEMENTATION
# =============================================================================

class GroqLLM(BaseLLM):
    """
    Wrapper for Groq API.
    
    Implements the same interface as Ollama for seamless integration.
    """
    
    def __init__(
        self, 
        model_name: Optional[str] = None, 
        temperature: float = 0.7,
        max_tokens: int = 8192,
        api_key: Optional[str] = None
    ):
        super().__init__(temperature)
        
        # Get API key from parameter, environment, or raise error
        self._api_key = api_key or os.getenv("groq_api_key") or os.getenv("GROQ_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Groq API key not found. Set 'groq_api_key' or 'GROQ_API_KEY' "
                "environment variable or pass api_key parameter."
            )
        
        # Import Groq client
        try:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        except ImportError:
            raise ImportError(
                "groq package is required for Groq support. "
                "Install with: pip install groq"
            )
        
        # Get model from parameter or environment
        default_model = os.getenv("model", "openai/gpt-oss-20b").strip('"')
        self._model_name = model_name or default_model
        self.max_tokens = max_tokens
        
        print(f"✓ Groq API initialized with model: {self._model_name}")
    
    def invoke(self, prompt: str) -> str:
        """
        Invoke Groq API with the given prompt.
        
        Args:
            prompt: The prompt text to send
            
        Returns:
            The generated text response
            
        Raises:
            Exception: If the API call fails
        """
        try:
            completion = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_completion_tokens=self.max_tokens,
                top_p=1,
                stream=True,
                stop=None
            )
            
            # Collect streamed response
            response_parts = []
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    response_parts.append(chunk.choices[0].delta.content)
            
            return ''.join(response_parts)
            
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")
    
    @property
    def model_name(self) -> str:
        return self._model_name


# Backward compatibility alias
GroqWrapper = GroqLLM


# =============================================================================
# FACTORY
# =============================================================================

class LLMFactory:
    """Factory class to create LLM clients based on provider."""
    
    PROVIDERS = {
        "ollama": OllamaLLM,
        "groq": GroqLLM,
    }
    
    @classmethod
    def create(
        cls, 
        provider: str = "ollama", 
        model_name: Optional[str] = None, 
        temperature: float = 0.7,
        **kwargs
    ) -> BaseLLM:
        """
        Create an LLM client based on the provider.
        
        Args:
            provider: Either "ollama" or "groq"
            model_name: Model name (defaults based on provider)
            temperature: Temperature for generation (0.0-1.0)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLM client instance
            
        Raises:
            ValueError: If provider is not supported
        """
        provider_lower = provider.lower()
        
        if provider_lower not in cls.PROVIDERS:
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Supported providers: {list(cls.PROVIDERS.keys())}"
            )
        
        llm_class = cls.PROVIDERS[provider_lower]
        
        # Build kwargs based on provider
        init_kwargs = {"temperature": temperature, **kwargs}
        
        if model_name:
            init_kwargs["model_name"] = model_name
        elif provider_lower == "ollama":
            init_kwargs["model_name"] = os.getenv("OLLAMA_MODEL", "llama3:latest")
        
        return llm_class(**init_kwargs)
    
    @classmethod
    def create_llm(
        cls, 
        provider: str = "ollama", 
        model_name: Optional[str] = None, 
        temperature: float = 0.7
    ) -> BaseLLM:
        """
        Alias for create() for backward compatibility.
        """
        return cls.create(provider=provider, model_name=model_name, temperature=temperature)
    
    @classmethod
    def register_provider(cls, name: str, llm_class: type) -> None:
        """
        Register a custom LLM provider.
        
        Args:
            name: Provider name
            llm_class: LLM class that implements BaseLLM
        """
        if not issubclass(llm_class, BaseLLM):
            raise TypeError(f"LLM class must inherit from BaseLLM")
        cls.PROVIDERS[name.lower()] = llm_class


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_ollama(model: str = "llama3:latest", temperature: float = 0.7) -> OllamaLLM:
    """Get an Ollama LLM client."""
    return LLMFactory.create("ollama", model_name=model, temperature=temperature)


def get_groq(model: Optional[str] = None, temperature: float = 0.7) -> GroqLLM:
    """Get a Groq LLM client."""
    return LLMFactory.create("groq", model_name=model, temperature=temperature)
