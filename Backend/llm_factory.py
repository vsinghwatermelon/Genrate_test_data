"""
LLM Factory Module

Provides a unified interface for both Ollama and Groq API.
Allows seamless switching between local Ollama models and Groq API.
"""

import os
from typing import Optional
from langchain_ollama import OllamaLLM
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class LLMFactory:
    """Factory class to create LLM clients based on provider."""
    
    @staticmethod
    def create_llm(provider: str = "ollama", model_name: Optional[str] = None, temperature: float = 0.7):
        """
        Create an LLM client based on the provider.
        
        Args:
            provider: Either "ollama" or "groq"
            model_name: Model name (defaults based on provider)
            temperature: Temperature for generation
            
        Returns:
            LLM client (either OllamaLLM or GroqWrapper)
        """
        if provider.lower() == "groq":
            return GroqWrapper(model_name=model_name, temperature=temperature)
        else:
            # Default to Ollama
            model = model_name or "llama3:latest"
            return OllamaLLM(model=model, temperature=temperature)


class GroqWrapper:
    """
    Wrapper for Groq API that provides a compatible interface with OllamaLLM.
    Implements the same invoke() method for seamless integration.
    """
    
    def __init__(self, model_name: Optional[str] = None, temperature: float = 0.7):
        """
        Initialize Groq client.
        
        Args:
            model_name: Groq model name (defaults to openai/gpt-oss-20b from .env)
            temperature: Temperature for generation
        """
        # Get API key from environment
        api_key = os.getenv("groq_api_key")
        if not api_key:
            raise ValueError("groq_api_key not found in environment variables. Please set it in .env file")
        
        self.client = Groq(api_key=api_key)
        
        # Get model from .env or use provided model_name
        default_model = os.getenv("model", "openai/gpt-oss-20b").strip('"')
        self.model = model_name or default_model
        self.temperature = temperature
        
        print(f"✓ Groq API initialized with model: {self.model}")
    
    def invoke(self, prompt: str) -> str:
        """
        Invoke Groq API with the given prompt.
        Compatible with OllamaLLM's invoke() method.
        
        Args:
            prompt: The prompt text to send to Groq
            
        Returns:
            The generated text response
        """
        try:
            # Create chat completion with streaming
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_completion_tokens=8192,
                top_p=1,
                stream=True,
                stop=None
            )
            
            # Collect streamed response
            response_text = ""
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    response_text += chunk.choices[0].delta.content
            
            return response_text
            
        except Exception as e:
            raise Exception(f"Groq API error: {str(e)}")
