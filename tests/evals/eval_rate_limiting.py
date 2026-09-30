import sys
import time
import pathlib
from unittest.mock import patch, MagicMock

import httpx
from openai import RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

# Setup path so we can import from app
_ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT_DIR))

from app.signal_extraction import call_llm

def build_rate_limit_error() -> RateLimitError:
    http_response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return RateLimitError(
        message="Rate limit reached for model `openai/gpt-oss-120b`",
        response=http_response,
        body={"error": {"message": "Rate limit reached", "type": "tokens", "code": "rate_limit_exceeded"}}
    )

def build_success_response() -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-mock",
        model="gpt-oss-120b",
        object="chat.completion",
        created=12345,
        choices=[
            Choice(
                index=0, 
                finish_reason="stop", 
                message=ChatCompletionMessage(content='{"status": "ok"}', role="assistant")
            )
        ]
    )

def evaluate_scenario(name: str, sequence_description: str, side_effect: list):
    print(f"\n[{name}]")
    print(f"Injected sequence: {sequence_description}")
    
    mock_client = MagicMock()
    mock_create = mock_client.chat.completions.create
    mock_create.side_effect = side_effect
    
    start_time = time.perf_counter()
    attempts_made = 0
    outcome = ""
    exception_type = "None"
    recovery = False
    
    with patch("app.signal_extraction._get_client", return_value=mock_client), \
         patch("app.signal_extraction.time.sleep", return_value=None):
        try:
            call_llm("System prompt", "User message")
            outcome = "Returned"
            recovery = True
        except Exception as e:
            outcome = "Raised"
            exception_type = type(e).__name__
            recovery = False
        
        attempts_made = mock_create.call_count
        
    duration = time.perf_counter() - start_time
    
    print(f"Attempts made: {attempts_made}")
    print(f"Outcome: {outcome}")
    print(f"Exception: {exception_type}")
    print(f"Recovery: {recovery}")
    print(f"Execution time (mocked): {duration * 1000:.2f}ms")

def main():
    print("=" * 80)
    print("  PROVIDER RATE LIMITING EVALUATION (POST-MITIGATION)")
    print("=" * 80)
    print("Target: app.signal_extraction.call_llm")
    print("Evaluation of post-mitigation behavior under injected HTTP 429 rate-limit failures.")
    print("Note: Execution time is not a meaningful performance metric because the provider is mocked.")
    print("=" * 80)
    
    error_429 = build_rate_limit_error()
    success = build_success_response()
    
    # 1. First returns 429, next succeeds
    evaluate_scenario(
        "Scenario 1",
        "1x HTTP 429 -> Success",
        [error_429, success]
    )
    
    # 2. First two return 429, third succeeds
    evaluate_scenario(
        "Scenario 2",
        "2x HTTP 429 -> Success",
        [error_429, error_429, success]
    )
    
    # 3. Persistent 429s (simulate up to 5)
    evaluate_scenario(
        "Scenario 3",
        "Persistent HTTP 429s",
        [error_429] * 5
    )
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
