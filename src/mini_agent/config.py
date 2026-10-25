DEFAULT_OLLAMA_URL = "http://192.168.1.76:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"

TEMPERATURE = 0.2   # agent prévisible, pas créatif
NUM_CTX = 8192      # fenêtre de contexte demandée à Ollama

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    ollama_url: str
    model: str
    temperature: float = TEMPERATURE
    num_ctx: int = NUM_CTX

    @property
    def chat_url(self) -> str:
        return f"{self.ollama_url}/api/chat"

    def options(self) -> dict:
        return {"temperature": self.temperature, "num_ctx": self.num_ctx}

def load_config() -> Config:
    url = os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    return Config(ollama_url=url.rstrip("/"), model=model)