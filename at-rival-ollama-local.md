# @TheRival Ollama Local Setup

Use this quick note when running Rival with a small local model.

## Recommended Model (Low Disk)

- Model tag: `qwen2.5:1b`
- Goal fit: relevant smack talk with low storage cost

## Required Environment Variables

```powershell
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen2.5:1b'
$env:RIVAL_REQUEST_TIMEOUT_SECONDS = '20'
$env:RIVAL_RUNTIME_MODE = 'go_live'
```

Increase timeout to `30` on slower CPUs.

## Pull and Verify Model

```bash
ollama serve
ollama pull qwen2.5:1b
ollama list
curl -s http://127.0.0.1:11434/api/tags
```

## Optional Upgrade Path

If `qwen2.5:1b` tone quality is too weak, step up to:

1. `qwen2.5:1.5b`
2. `qwen2.5:3b`
