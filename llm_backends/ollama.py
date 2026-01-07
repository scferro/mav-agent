"""
Ollama Model Interface for MAVLink Agent
Handles communication with Ollama models
"""

from typing import Dict, Any, Optional, List
import json
import requests
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

from config import get_model_settings

class OllamaInterface:
    """Interface for Ollama model communication"""
    
    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        model_settings = get_model_settings()
        
        self.model_name = model_name or model_settings['name']
        self.base_url = base_url or model_settings['base_url']
        self.temperature = model_settings['temperature']
        self.top_p = model_settings['top_p']
        self.top_k = model_settings['top_k']
        self.timeout = 60
        self.max_tokens = model_settings['max_tokens']
        
        self._llm = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the Ollama LLM instance"""
        try:
            self._llm = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                timeout=self.timeout,
                num_predict=self.max_tokens
                # Removed format="json" - this breaks LangChain tool calling
            )
        except Exception as e:
            raise ConnectionError(f"Failed to initialize Ollama model: {str(e)}")
    
    def get_llm(self) -> BaseChatModel:
        """Get the LangChain LLM instance"""
        if self._llm is None:
            self._initialize_model()
        return self._llm
    
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> List[str]:
        """List available models in Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception:
            return []
    
    def is_model_available(self, model_name: Optional[str] = None) -> bool:
        """Check if specific model is available"""
        model = model_name or self.model_name
        available_models = self.list_models()
        return model in available_models
    
    def test_connection(self) -> tuple[bool, str]:
        """Test connection to Ollama and model availability"""
        # Check if Ollama is running
        if not self.is_available():
            return False, f"Ollama service not available at {self.base_url}"
        
        # Check if model is available
        if not self.is_model_available():
            available_models = self.list_models()
            model_list = ", ".join(available_models) if available_models else "None"
            return False, (
                f"Model '{self.model_name}' not found. "
                f"Available models: {model_list}. "
                f"Use 'ollama pull {self.model_name}' to download it."
            )
        # Test simple generation
        try:
            llm = self.get_llm()
            response = llm.invoke("Test")
            return True, "Connection successful"
        except Exception as e:
            return False, f"Model test failed: {str(e)}"