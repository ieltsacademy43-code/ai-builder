"""
LLM Manager for AI Builder.
Provides a unified interface to multiple LLM providers (OpenAI, Claude, Gemini).
Automatically selects the best available provider and allows adding more later.
Uses only the Python standard library (urllib) for HTTP — no external dependencies.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from core.logger import get_logger
from config.settings import get_config
from memory.memory_store import get_memory

log = get_logger("llm")


class LLMResponse:
    """Wraps an LLM generation result with metadata."""

    def __init__(self, text, provider, model, success=True, error=None,
                 prompt_chars=0, response_chars=0, duration=0):
        self.text = text
        self.provider = provider
        self.model = model
        self.success = success
        self.error = error
        self.prompt_chars = prompt_chars
        self.response_chars = response_chars
        self.duration = duration
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "success": self.success,
            "error": self.error,
            "prompt_chars": self.prompt_chars,
            "response_chars": self.response_chars,
            "duration": self.duration,
            "timestamp": self.timestamp,
        }


class LLMProvider:
    """Base class for LLM providers."""

    name = "base"
    display_name = "Base Provider"
    default_model = ""
    default_max_tokens = 4096
    default_temperature = 0.7

    def __init__(self, config=None):
        self.config = config or get_config()
        self.api_key = self._get_api_key()
        self.model = self._get_model()
        self.base_url = self._get_base_url()

    def _get_api_key(self):
        return self.config.get(f"llm.{self.name}.api_key", "") or ""

    def _get_model(self):
        return self.config.get(f"llm.{self.name}.model", "") or self.default_model

    def _get_base_url(self):
        return self.config.get(f"llm.{self.name}.base_url", "") or self._default_base_url()

    def _default_base_url(self):
        return ""

    def available(self):
        """Return True if this provider is configured and ready."""
        return bool(self.api_key)

    def generate(self, prompt, system_prompt=None, max_tokens=None, temperature=None):
        """Generate a response. Returns an LLMResponse."""
        raise NotImplementedError("Subclasses must implement generate()")

    def _post_json(self, url, headers, payload, timeout=120):
        """POST JSON to a URL and return parsed response. Uses urllib only."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        start = datetime.now()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                duration = (datetime.now() - start).total_seconds()
                return json.loads(body), None, duration
        except urllib.error.HTTPError as e:
            duration = (datetime.now() - start).total_seconds()
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            return None, f"HTTP {e.code}: {error_body[:500]}", duration
        except urllib.error.URLError as e:
            duration = (datetime.now() - start).total_seconds()
            return None, f"URL Error: {e.reason}", duration
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            return None, str(e), duration

    def info(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "model": self.model,
            "available": self.available(),
            "has_api_key": bool(self.api_key),
            "base_url": self.base_url,
        }


class OpenAIProvider(LLMProvider):
    """OpenAI GPT API provider."""

    name = "openai"
    display_name = "OpenAI"
    default_model = "gpt-4o"
    default_max_tokens = 4096

    def _default_base_url(self):
        return "https://api.openai.com/v1"

    def generate(self, prompt, system_prompt=None, max_tokens=None, temperature=None):
        if not self.available():
            return LLMResponse("", self.name, self.model, success=False,
                               error="No API key configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature if temperature is not None else self.default_temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        data, error, duration = self._post_json(url, headers, payload)
        if error:
            return LLMResponse("", self.name, self.model, success=False,
                               error=error, prompt_chars=len(prompt), duration=duration)
        try:
            text = data["choices"][0]["message"]["content"]
            return LLMResponse(text, self.name, self.model, success=True,
                               prompt_chars=len(prompt), response_chars=len(text),
                               duration=duration)
        except (KeyError, IndexError, TypeError) as e:
            return LLMResponse("", self.name, self.model, success=False,
                               error=f"Parse error: {e}", prompt_chars=len(prompt),
                               duration=duration)


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    name = "claude"
    display_name = "Claude"
    default_model = "claude-sonnet-4-20250514"
    default_max_tokens = 4096

    def _default_base_url(self):
        return "https://api.anthropic.com/v1"

    def generate(self, prompt, system_prompt=None, max_tokens=None, temperature=None):
        if not self.available():
            return LLMResponse("", self.name, self.model, success=False,
                               error="No API key configured")

        messages = [{"role": "user", "content": prompt}]
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "messages": messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if temperature is not None:
            payload["temperature"] = temperature

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/messages"
        data, error, duration = self._post_json(url, headers, payload)
        if error:
            return LLMResponse("", self.name, self.model, success=False,
                               error=error, prompt_chars=len(prompt), duration=duration)
        try:
            text = data["content"][0]["text"]
            return LLMResponse(text, self.name, self.model, success=True,
                               prompt_chars=len(prompt), response_chars=len(text),
                               duration=duration)
        except (KeyError, IndexError, TypeError) as e:
            return LLMResponse("", self.name, self.model, success=False,
                               error=f"Parse error: {e}", prompt_chars=len(prompt),
                               duration=duration)


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    name = "gemini"
    display_name = "Gemini"
    default_model = "gemini-1.5-pro"
    default_max_tokens = 4096

    def _default_base_url(self):
        return "https://generativelanguage.googleapis.com/v1beta"

    def generate(self, prompt, system_prompt=None, max_tokens=None, temperature=None):
        if not self.available():
            return LLMResponse("", self.name, self.model, success=False,
                               error="No API key configured")

        contents = [{"parts": [{"text": prompt}]}]
        gen_config = {
            "maxOutputTokens": max_tokens or self.default_max_tokens,
            "temperature": temperature if temperature is not None else self.default_temperature,
        }
        payload = {"contents": contents, "generationConfig": gen_config}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        data, error, duration = self._post_json(url, headers, payload)
        if error:
            return LLMResponse("", self.name, self.model, success=False,
                               error=error, prompt_chars=len(prompt), duration=duration)
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return LLMResponse(text, self.name, self.model, success=True,
                               prompt_chars=len(prompt), response_chars=len(text),
                               duration=duration)
        except (KeyError, IndexError, TypeError) as e:
            return LLMResponse("", self.name, self.model, success=False,
                               error=f"Parse error: {e}", prompt_chars=len(prompt),
                               duration=duration)


# Registry of built-in providers
_BUILTIN_PROVIDERS = {
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
}


class LLMManager:
    """Manages multiple LLM providers and auto-selects the best available."""

    def __init__(self, config=None, memory=None):
        self.config = config or get_config()
        self.memory = memory or get_memory()
        self._providers = {}
        self._preferred_order = self.config.get("llm.preferred", "openai,claude,gemini")
        self._init_providers()

    def _init_providers(self):
        """Instantiate all built-in providers."""
        for name, cls in _BUILTIN_PROVIDERS.items():
            try:
                self._providers[name] = cls(config=self.config)
            except Exception as e:
                log.warning(f"Failed to init provider '{name}': {e}")

    def register_provider(self, name, provider):
        """Register a custom LLM provider."""
        self._providers[name] = provider
        log.info(f"Registered LLM provider: {name}")

    def get_provider(self, name):
        """Get a specific provider by name."""
        return self._providers.get(name)

    def list_providers(self):
        """Return info for all registered providers."""
        return {name: p.info() for name, p in self._providers.items()}

    def list_available(self):
        """Return names of available providers (with API keys configured)."""
        return [name for name, p in self._providers.items() if p.available()]

    def get_best_provider(self):
        """Return the best available provider based on preferred order."""
        preferred = [p.strip() for p in self._preferred_order.split(",") if p.strip()]
        for name in preferred:
            provider = self._providers.get(name)
            if provider and provider.available():
                return provider
        for name, provider in self._providers.items():
            if provider.available():
                return provider
        return None

    def generate(self, prompt, system_prompt=None, model=None, max_tokens=None,
                 temperature=None, provider_name=None):
        """
        Generate text using the best available provider.

        If provider_name is specified, use that provider.
        If model is specified, it overrides the provider's default model.
        Returns an LLMResponse.
        """
        provider = None
        if provider_name:
            provider = self._providers.get(provider_name)
            if not provider:
                return LLMResponse("", "none", "", success=False,
                                   error=f"Unknown provider: {provider_name}")
            if not provider.available():
                return LLMResponse("", provider_name, "", success=False,
                                   error=f"Provider '{provider_name}' not available (no API key)")
        else:
            provider = self.get_best_provider()

        if not provider:
            log.warning("No LLM provider available — falling back to rule-based mode")
            return LLMResponse("", "none", "", success=False,
                               error="No LLM provider available. Set an API key in config "
                                     "(llm.openai.api_key, llm.claude.api_key, or "
                                     "llm.gemini.api_key) or env vars "
                                     "AIBUILDER_LLM_OPENAI_API_KEY, etc.")

        if model:
            provider.model = model

        log.info(f"Generating with {provider.name} ({provider.model})...")
        response = provider.generate(prompt, system_prompt=system_prompt,
                                     max_tokens=max_tokens, temperature=temperature)

        self._record_usage(response)
        if response.success:
            log.info(f"LLM response: {response.response_chars} chars in {response.duration:.2f}s")
        else:
            log.warning(f"LLM generation failed ({provider.name}): {response.error}")
        return response

    def _record_usage(self, response):
        """Record LLM usage in memory for analytics."""
        self.memory.append_history("llm_usage", "calls", {
            "provider": response.provider,
            "model": response.model,
            "success": response.success,
            "error": response.error,
            "prompt_chars": response.prompt_chars,
            "response_chars": response.response_chars,
            "duration": response.duration,
            "timestamp": response.timestamp,
        })

    def is_available(self):
        """Return True if at least one provider is available."""
        return len(self.list_available()) > 0

    def status(self):
        """Return a summary of LLM manager state."""
        available = self.list_available()
        return {
            "providers": self.list_providers(),
            "available": available,
            "best": available[0] if available else None,
            "preferred_order": self._preferred_order,
            "total_providers": len(self._providers),
        }


def get_llm_manager():
    """Return a singleton LLMManager instance."""
    if not hasattr(get_llm_manager, "_instance"):
        get_llm_manager._instance = LLMManager()
    return get_llm_manager._instance