import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from openai import RateLimitError
import httpx

from app.api import app

client = TestClient(app)

def build_rate_limit_error() -> RateLimitError:
    http_response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return RateLimitError(
        message="Rate limit reached for model `openai/gpt-oss-120b`",
        response=http_response,
        body={"error": {"message": "Rate limit reached", "type": "tokens", "code": "rate_limit_exceeded"}}
    )

def test_api_rate_limit_persistent_503():
    """Verify that a persistent provider rate limit correctly maps to an HTTP 503 response from our API."""
    mock_client = MagicMock()
    mock_create = mock_client.chat.completions.create
    # Persistent failures (at least 3 to trigger the ProviderRateLimitError)
    mock_create.side_effect = [build_rate_limit_error()] * 5
    
    with patch("app.signal_extraction._get_client", return_value=mock_client), \
         patch("app.signal_extraction.time.sleep", return_value=None):
         
        payload = {
            "name": "Jane Doe",
            "company": "Example Corp",
            "inquiry": "We need 50 licenses of your enterprise software immediately."
        }
        
        response = client.post("/qualify", json=payload)
        
        assert response.status_code == 503
        assert response.json() == {"detail": "Upstream AI provider rate limit exceeded. Please try again later."}
        
        # Verify it actually attempted 3 times before giving up
        assert mock_create.call_count == 3
