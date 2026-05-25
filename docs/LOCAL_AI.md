# Local AI Configuration

NexusIntel tidak mengunduh model otomatis. Operator menjalankan runtime lokal sendiri, lalu menghubungkannya melalui Settings atau environment variable.

## Mode

- `rules`: default, tanpa model, semua reasoning memakai rule engine.
- `ollama`: endpoint kompatibel Ollama, default `http://localhost:11434`.
- `llamacpp`: endpoint kompatibel llama.cpp server.
- `openai_compatible`: endpoint chat-completions kompatibel OpenAI.

## Environment

```bash
NEXUS_AI_MODE=rules|ollama|llamacpp|openai_compatible
NEXUS_AI_ENDPOINT=http://localhost:11434
NEXUS_AI_MODEL=
NEXUS_AI_CONTEXT_TOKENS=4096
NEXUS_AI_MAX_TOKENS=700
NEXUS_AI_TEMPERATURE=0.1
NEXUS_AI_RAM_PROFILE=tiny|small|balanced
NEXUS_AI_ENABLE_SUMMARIZATION=true
NEXUS_AI_ENABLE_JSON_MODE=true
```

## RAM Profiles

- `tiny`: 2-4GB, classification, short summary, next actions.
- `small`: 4-8GB, stronger reasoning and concise briefings.
- `balanced`: 8-16GB, broader analyst summaries.

## Data Minimization

Raw evidence payload besar tidak dikirim ke model. Context memakai compact evidence cards: ID, source, source URL, hash, excerpt/validation status. Case memory menyimpan ringkasan dan evidence IDs, bukan payload mentah besar.
