"""
UnifyOps  -  Model Armor Service (Phase 9.2)

Provides input and output validation shielding for Vertex AI LLM calls,
filtering prompt injections, jailbreaks, and sensitive data leakage.
"""

import os
import re


class SecurityBlockException(Exception):
    """Exception raised when Model Armor blocks a request."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


class ModelArmorService:
    """Shared Model Armor interface providing prompt and response shielding."""

    def __init__(self) -> None:
        self.enabled = False
        # If GCP credentials and specific Vertex AI Model Armor config exists:
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            # Can load real Model Armor client endpoint in the future
            self.enabled = True

    def screen_interaction(self, text: str, agent_name: str = "general") -> str:
        """
        Screens prompt input or response output for injections, jailbreaks, and leaks.
        Raises SecurityBlockException if text is blocked.
        Returns the text unchanged if it passes verification.
        """
        # Load store lazily to avoid circular imports
        from app.core.store import store

        # Injection indicators
        injection_patterns = [
            r"\bignore\b.*\binstructions\b",
            r"\bignore\b.*\bprior\b",
            r"\bsystem\b.*\boverride\b",
            r"\bjailbreak\b",
            r"\bacting\b.*\bas\b.*\bdeveloper\b",
            r"\bdo\b.*\banything\b.*\bnow\b",
            r"\boverride\b.*\bsafety\b",
            r"\bbypass\b.*\bsecurity\b",
            r"\bdelete\b.*\bdatabase\b",
        ]

        text_lower = text.lower()
        blocked = False
        reason = ""

        # Scan for injection attacks
        for pattern in injection_patterns:
            if re.search(pattern, text_lower):
                blocked = True
                reason = "Potential Prompt Injection / Jailbreak attempt detected."
                break

        # Scan for credentials or raw secrets leakage
        if "gsk_" in text or "key = " in text_lower or "api_key" in text_lower:
            # Check if there is an actual high-entropy API key signature
            if re.search(r"[a-zA-Z0-9_-]{32,}", text):
                blocked = True
                reason = "Sensitive credential leak blocked (API Key)."

        prompt_snippet = text[:120] + ("..." if len(text) > 120 else "")

        if blocked:
            # Log block event centrally in datastore telemetry
            store.log_model_armor_event(
                source=agent_name,
                status="blocked",
                prompt_snippet=prompt_snippet,
                block_reason=reason,
            )
            raise SecurityBlockException(
                message="Security Block: The request was flagged as violating safety and security policies.",
                reason=reason,
            )

        # Log allowed event for traffic telemetry (limited to snippets)
        store.log_model_armor_event(
            source=agent_name,
            status="allowed",
            prompt_snippet=prompt_snippet,
            block_reason="",
        )

        return text


# Singleton
model_armor_service = ModelArmorService()
