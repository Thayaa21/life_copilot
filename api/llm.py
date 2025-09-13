import os, requests, json

class LLMError(Exception): ...

def llm_complete(system: str, user: str) -> str:
    prov = (os.getenv("LLM_PROVIDER") or "ollama").lower()
    if prov == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        try:
            r = requests.post("http://127.0.0.1:11434/api/chat", json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "options": {"temperature": 0.2, "num_predict": 256},
                "stream": False  # <-- IMPORTANT: disable streaming
            }, timeout=90)
            r.raise_for_status()
            data = r.json()
            # Expected non-stream schema from Ollama:
            # { "message": { "role":"assistant", "content":"..." }, ... }
            if isinstance(data, dict) and "message" in data:
                return (data["message"].get("content") or "").strip()
            # Fallback: try to extract text-like fields
            if isinstance(data, dict):
                for k in ("content","text","response"):
                    if isinstance(data.get(k), str):
                        return data[k].strip()
            raise LLMError(f"unexpected_response_schema: {data}")
        except requests.exceptions.JSONDecodeError as e:
            raise LLMError(f"ollama_json_decode_error: {e}; raw={r.text[:300]!r}")
        except Exception as e:
            raise LLMError(f"ollama_error: {e}")
    else:
        raise LLMError(f"unsupported_provider:{prov}")