"""
Reusable client for the Vercel AI Gateway "Jev" typesafe extraction model.

Usage:
    client = JevClient()                          # reads AI_GATEWAY_API_KEY from env
    result = client.extract("some text", questions)
"""

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class JevClient:
    """Thin wrapper around the Vercel AI Gateway typesafe endpoint."""

    DEFAULT_ENDPOINT = "https://ai-gateway.vercel.sh/v1/evaluate"
    DEFAULT_MODEL = "typesafe-ai/jev"

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("AI_GATEWAY_API_KEY", "")
        self.endpoint = endpoint or self.DEFAULT_ENDPOINT
        self.model = model or self.DEFAULT_MODEL

        if not self.api_key:
            raise RuntimeError(
                "AI_GATEWAY_API_KEY is not set. "
                "Add it to your .env or export it before running Jev tests."
            )

    def extract(
        self,
        state: str,
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Send a typesafe extraction request and return the parsed response.

        Parameters
        ----------
        state : str
            The raw text for the model to analyse (e.g. inquiry text).
        questions : dict
            A mapping of field names to Jev question configs, each containing
            ``type``, ``instructions``, and ``options``.

        Returns
        -------
        dict
            The full JSON response from the gateway.
        """
        payload = {
            "model": self.model,
            "state": state,
            "questions": questions,
        }

        logger.debug("Jev request → %s", payload)

        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=30,
        )

        if not response.ok:
            # Include the response body so we can debug payload issues
            raise requests.exceptions.HTTPError(
                f"{response.status_code} {response.reason}: {response.text}",
                response=response,
            )


        data = response.json()
        logger.debug("Jev response ← %s", data)
        return data
