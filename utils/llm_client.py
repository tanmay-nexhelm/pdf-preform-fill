"""
LLM client abstraction layer supporting OpenAI and Anthropic (Claude) models.

Allows easy switching between providers and models via configuration.
"""

import json
import os
from typing import Dict, Optional, List
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """
    Abstraction layer for LLM providers (OpenAI, Anthropic).

    Supports:
    - OpenAI: gpt-4o, gpt-4o-mini
    - Anthropic: claude-sonnet-4-5-20250929, claude-haiku-4-5-20251001
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM client with configurable provider and model.

        Args:
            provider: "openai" or "anthropic" (defaults to env LLM_PROVIDER or "openai")
            model: Model name (defaults to env LLM_MODEL or provider default)
        """
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai").lower()

        # Default models for each provider
        default_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-haiku-4-5-20251001"
        }

        self.model = model or os.getenv("LLM_MODEL", default_models.get(self.provider, "gpt-4o-mini"))

        # Initialize appropriate client
        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            raise ValueError(f"Unsupported provider: {self.provider}. Use 'openai' or 'anthropic'")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0
    ) -> Dict:
        """
        Generate JSON response from LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User query/task
            temperature: Sampling temperature (0 = deterministic)

        Returns:
            Parsed JSON dict
        """
        if self.provider == "openai":
            return self._generate_openai(system_prompt, user_prompt, temperature)
        elif self.provider == "anthropic":
            return self._generate_anthropic(system_prompt, user_prompt, temperature)

    def _generate_openai(self, system_prompt: str, user_prompt: str, temperature: float) -> Dict:
        """Generate response using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"OpenAI API error: {e}")
            raise

    def _generate_anthropic(self, system_prompt: str, user_prompt: str, temperature: float) -> Dict:
        """Generate response using Anthropic Claude API."""
        try:
            # Combine system and user prompts for Claude
            # Add explicit JSON instruction
            combined_prompt = f"""{system_prompt}

{user_prompt}

IMPORTANT: You must return ONLY valid JSON. Do not include any text before or after the JSON object."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": combined_prompt}
                ]
            )

            # Extract text content
            response_text = response.content[0].text.strip()

            # Try to parse JSON
            # Sometimes Claude adds markdown code blocks, so handle that
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove ```

            response_text = response_text.strip()

            return json.loads(response_text)

        except json.JSONDecodeError as e:
            print(f"Claude returned invalid JSON: {e}")
            print(f"Response text: {response_text[:500]}...")
            raise
        except Exception as e:
            print(f"Anthropic API error: {e}")
            raise

    def get_info(self) -> str:
        """Return string describing current configuration."""
        return f"{self.provider.upper()}: {self.model}"


# Global instance (can be configured via environment variables)
_default_client = None


def get_llm_client(provider: Optional[str] = None, model: Optional[str] = None) -> LLMClient:
    """
    Get or create LLM client instance.

    Args:
        provider: Override default provider
        model: Override default model

    Returns:
        LLMClient instance
    """
    global _default_client

    if provider or model:
        # Create new client with specific configuration
        return LLMClient(provider=provider, model=model)

    # Return or create default client
    if _default_client is None:
        _default_client = LLMClient()

    return _default_client
