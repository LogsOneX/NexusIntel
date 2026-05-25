# Local AI Models

NexusIntel supports local AI orchestration without automatic model downloads.

## Modes

- `rules`: deterministic engine only.
- `ollama`: Ollama-compatible chat endpoint.
- `llamacpp`: llama.cpp server endpoint.
- `openai_compatible`: OpenAI-compatible endpoint if configured.

## Profiles

- `tiny`: 2-4GB RAM, short summaries and next actions.
- `small`: 4-8GB RAM, stronger reasoning.
- `balanced`: 8-16GB RAM, wider summaries.

## Guardrails

- Raw payloads are not sent to models by default.
- Compact evidence cards are used instead.
- LLM output cannot upgrade validator labels without evidence.
- If evidence is missing, replies must say insufficient evidence.
