from abc import ABC, abstractmethod
from typing import Optional
from modules.shared.config import get_config

config = get_config()

class BaseLLM(ABC):
    """Simple interface for LLM interaction."""
    @abstractmethod
    def invoke(self, prompt: str) -> str: pass

class OllamaLLM(BaseLLM):
    """Ollama client implementation."""
    def __init__(self, model: str, temperature: float = 0.7):
        try:
            from langchain_ollama import OllamaLLM as LangchainOllama
            self.client = LangchainOllama(
                model=model or config.llm.ollama_model,
                base_url=config.llm.ollama_base_url,
                temperature=temperature
            )
        except ImportError:
            raise ImportError("Ollama support missing. Run: pip install langchain-ollama")
            
    def invoke(self, prompt: str) -> str: return self.client.invoke(prompt)

class GroqLLM(BaseLLM):
    """Groq client implementation."""
    def __init__(self, model: str, temperature: float = 0.7):
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Groq support missing. Run: pip install groq")
            
        api_key = config.llm.groq_api_key
        if not api_key:
            raise ValueError("Groq API key missing. Check your .env file for 'groq_api_key'.")
            
        self.model = model or config.llm.groq_model
        self.temperature = temperature
        self.client = Groq(api_key=api_key)

    def invoke(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature
        )
        return completion.choices[0].message.content

class LLMService:
    """Factory for creating LLM clients."""
    PROVIDERS = {"ollama": OllamaLLM, "groq": GroqLLM}
    
    @classmethod
    def get_llm(cls, provider: str, model: Optional[str] = None) -> BaseLLM:
        llm_class = cls.PROVIDERS.get(provider.lower())
        if not llm_class: raise ValueError(f"Unknown provider: {provider}")
        return llm_class(model=model)
