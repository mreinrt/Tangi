"""
Multi-Provider API client for online mode
Supports: NVIDIA NIM, OpenAI, Together AI, DeepSeek, and any OpenAI-compatible endpoint
"""

import os
import logging
import requests
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class OnlineAPIClient:
    """
    Universal client for any OpenAI-compatible API endpoint.
    Supports: NVIDIA NIM, OpenAI, Together AI, DeepSeek, and more.
    
    Just change the API_BASE_URL to switch providers:
    - NVIDIA NIM: https://integrate.api.nvidia.com/v1
    - OpenAI: https://api.openai.com/v1
    - Together AI: https://api.together.xyz/v1
    - DeepSeek: https://api.deepseek.com/v1
    """
    
    DEFAULT_API_KEY = ""  # User will set this
    DEFAULT_MODEL = "mistralai/mistral-nemotron"  # NVIDIA's best coding model
    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"  # NVIDIA NIM default
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, 
                 base_url: Optional[str] = None, org_id: Optional[str] = None):
        self._api_key = api_key or self.get_api_key()
        self.model = model or self.get_model()
        self.base_url = base_url or self.get_base_url() or self.DEFAULT_BASE_URL
        self.org_id = org_id or self.get_org_id()
        self.conversation_history = []
        self.max_history = 10  # Keep last 10 exchanges
    
    # ==================== API KEY PROPERTY (Always reloads from settings) ====================
    
    @property
    def api_key(self) -> str:
        """Property that always returns the current API key from settings"""
        return self.get_api_key()
    
    @api_key.setter
    def api_key(self, value: str):
        """Set the API key (also saves to settings)"""
        self._api_key = value
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        settings.setValue("api_key", value)
        
        # Detect provider from key format for logging
        if value.startswith("nvapi-"):
            logger.info("NVIDIA NIM API key saved")
        elif value.startswith("sk-"):
            logger.info("OpenAI/DeepSeek API key saved")
        else:
            logger.info("API key saved")
    
    def ensure_authenticated(self) -> bool:
        """Ensure the client has a valid API key loaded from settings"""
        self._api_key = self.get_api_key()
        return bool(self._api_key)
    
    # ==================== BASE URL MANAGEMENT ====================
    
    def set_base_url(self, base_url: str):
        """Set the API base URL (for switching providers)"""
        self.base_url = base_url.rstrip('/')  # Remove trailing slash if present
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        settings.setValue("api_base_url", base_url)
        logger.info(f"API base URL set to: {base_url}")
    
    def get_base_url(self) -> str:
        """Get base URL from settings"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        saved_url = settings.value("api_base_url", "")
        return saved_url if saved_url else self.DEFAULT_BASE_URL
    
    # ==================== API KEY MANAGEMENT ====================
    
    def set_api_key(self, api_key: str):
        """Set the API key"""
        self.api_key = api_key  # This uses the setter property
    
    def get_api_key(self) -> str:
        """Get API key from settings"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        api_key = settings.value("api_key", "")
        
        # Try to migrate from old key if new one is empty
        if not api_key:
            old_key = settings.value("openai_api_key", "")
            if old_key:
                api_key = old_key
                settings.setValue("api_key", api_key)
                settings.remove("openai_api_key")
                logger.info("Migrated API key from old settings")
        
        return api_key if api_key else ""
    
    # ==================== ORGANIZATION ID (OpenAI specific) ====================
    
    def set_org_id(self, org_id: str):
        """Set organization ID (optional - for OpenAI enterprise accounts)"""
        self.org_id = org_id
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        settings.setValue("org_id", org_id)
        logger.info(f"Organization ID saved")
    
    def get_org_id(self) -> str:
        """Get organization ID from settings"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        return settings.value("org_id", "")
    
    # ==================== MODEL MANAGEMENT ====================
    
    def set_model(self, model: str):
        """Set the model to use"""
        self.model = model
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        settings.setValue("model", model)
        logger.info(f"Model set to: {model}")
    
    def get_model(self) -> str:
        """Get model from settings"""
        from PyQt6.QtCore import QSettings
        settings = QSettings("Tangi", "Tangi")
        model = settings.value("model", "")
        
        # Try to migrate from old key if new one is empty
        if not model:
            old_model = settings.value("openai_model", "")
            if old_model:
                model = old_model
                settings.setValue("model", model)
                settings.remove("openai_model")
                logger.info(f"Migrated model from old settings: {model}")
        
        return model if model else self.DEFAULT_MODEL
    
    # ==================== CONVERSATION HISTORY ====================
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def add_to_history(self, role: str, content: str):
        """Add message to history"""
        self.conversation_history.append({"role": role, "content": content})
        # Trim if too long
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history * 2:]
    
    # ==================== MESSAGE SENDING ====================
    
    def send_message(self, message: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a message to the API and return response.
        Works with any OpenAI-compatible endpoint.
        """
        # ALWAYS reload API key from settings (critical fix)
        current_api_key = self.get_api_key()
        
        if not current_api_key:
            raise ValueError("API key not set. Please configure in Preferences.")
        
        # Build messages
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        headers = {
            "Authorization": f"Bearer {current_api_key}",
            "Content-Type": "application/json"
        }
        
        # Add organization ID if set (only applies to OpenAI)
        if self.org_id:
            headers["OpenAI-Organization"] = self.org_id
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.95,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        # NVIDIA NIM specific: Add extra parameters for better coding
        if "nvidia" in self.base_url or current_api_key.startswith("nvapi-"):
            payload["temperature"] = 0.2  # Lower temperature for code
            payload["top_p"] = 0.95
        
        try:
            endpoint = f"{self.base_url}/chat/completions"
            logger.info(f"Sending request to: {endpoint} with model: {self.model}")
            
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            
            # Track token usage if available
            if "usage" in result:
                usage = result["usage"]
                logger.debug(f"Token usage - Prompt: {usage.get('prompt_tokens', 0)}, "
                           f"Completion: {usage.get('completion_tokens', 0)}, "
                           f"Total: {usage.get('total_tokens', 0)}")
            
            # Add to history
            self.add_to_history("user", message)
            self.add_to_history("assistant", reply)
            
            logger.info(f"Response received: {len(reply)} chars")
            return reply
            
        except requests.exceptions.Timeout:
            raise TimeoutError(f"API request timed out after 60 seconds to {self.base_url}")
        except requests.exceptions.RequestException as e:
            error_detail = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if "error" in error_data:
                        error_detail = f" - {error_data['error'].get('message', str(e))}"
                except:
                    pass
            raise ConnectionError(f"API error: {str(e)}{error_detail}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {str(e)}")
    
    # ==================== CONNECTION TESTING ====================
    
    def test_connection(self) -> bool:
        """Test API connection with a simple message"""
        try:
            # Save current history
            saved_history = self.conversation_history.copy()
            self.conversation_history = []
            
            # Send test message (short to avoid token usage)
            response = self.send_message("Say 'OK' only, nothing else.")
            
            # Restore history
            self.conversation_history = saved_history
            
            # Check if response contains OK
            if "OK" in response.upper():
                logger.info("Connection test successful")
                return True
            else:
                logger.warning(f"Unexpected test response: {response}")
                return True  # Still consider it a success if we got a response
                
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    # ==================== PROVIDER INFO ====================
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get information about the current provider"""
        if "integrate.api.nvidia.com" in self.base_url:
            return {
                "name": "NVIDIA NIM",
                "free_tier": "40 requests per minute",
                "credit_card": "Not required",
                "best_for": "Coding with Mistral-Nemotron (92.68% HumanEval)"
            }
        elif "api.openai.com" in self.base_url:
            return {
                "name": "OpenAI",
                "free_tier": "Requires payment method",
                "credit_card": "Required",
                "best_for": "General purpose with GPT-4o"
            }
        elif "api.together.xyz" in self.base_url:
            return {
                "name": "Together AI",
                "free_tier": "Free credits on signup",
                "credit_card": "Optional for free tier",
                "best_for": "Various open models"
            }
        elif "api.deepseek.com" in self.base_url:
            return {
                "name": "DeepSeek",
                "free_tier": "5M tokens for new accounts",
                "credit_card": "Not required",
                "best_for": "Cost-effective coding"
            }
        else:
            return {
                "name": "Custom API",
                "free_tier": "Check provider",
                "credit_card": "Varies",
                "best_for": "Custom endpoints"
            }


__all__ = ['OnlineAPIClient']