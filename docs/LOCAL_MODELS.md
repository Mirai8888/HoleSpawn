# Local model support

HoleSpawn can use **local models** via any **OpenAI-compatible API** (Ollama, LM Studio, vLLM, etc.). This reduces cost, keeps data local, and works offline once the model is pulled.

## Quick start (Ollama)

1. Install [Ollama](https://ollama.com) and pull a model:
   ```bash
   ollama pull llama3.1:8b
   ```
2. Run HoleSpawn with the local preset:
   ```bash
   python -m holespawn.build_site data/posts.txt --local-model ollama-llama3
   ```
   Or set env and run as usual:
   ```bash
   set LLM_API_BASE=http://localhost:11434/v1
   set LLM_MODEL=llama3.1:8b
   python -m holespawn.build_site data/posts.txt
   ```

## Presets (config)

In code or via env you can use presets from `holespawn.config.LOCAL_MODEL_PRESETS`:

| Preset            | API base                     | Model              | Notes                    |
|-------------------|------------------------------|--------------------|--------------------------|
| `ollama-llama3`   | http://localhost:11434/v1    | llama3.1:8b        | Good balance             |
| `ollama-mistral`  | http://localhost:11434/v1    | mistral:7b         | Faster, lighter          |
| `lmstudio`        | http://localhost:1234/v1     | local-model        | LM Studio default        |
| `vllm`            | http://localhost:8000/v1     | meta-llama/...     | Production inference     |

## CLI

- **`--local-model PRESET`** — Use a preset (`ollama-llama3`, `ollama-mistral`, `lmstudio`, `vllm`).
- **`--model-endpoint URL`** — Custom API base (e.g. `http://localhost:11434/v1`).
- **`--model-name NAME`** — Model name for that endpoint.

Examples:

```bash
# Preset
python -m holespawn.build_site data/posts.txt --local-model ollama-llama3

# Custom endpoint + model
python -m holespawn.build_site data/posts.txt --model-endpoint http://localhost:11434/v1 --model-name mistral:7b

# Discord + local
python -m holespawn.build_site --discord data/sample_discord_export.json --local-model ollama-llama3
```

## Environment variables

- **`LLM_API_BASE`** — OpenAI-compatible API base URL. When set, HoleSpawn uses this instead of Anthropic/OpenAI/Google.
- **`LLM_MODEL`** — Model name for that API (e.g. `llama3.1:8b`).
- **`LLM_API_KEY`** — Optional; for local Ollama you can leave unset or use `ollama`.

## When to use local vs cloud

| Use local when        | Use cloud when                |
|-----------------------|--------------------------------|
| Privacy / data on-box | Best possible copy/design      |
| No API spend          | No local GPU / RAM            |
| Offline or air-gapped | Fast iteration (no setup)     |
| Discord hybrid (NLP does heavy lifting) | Single-page + design system (many calls) |

## Architecture (NLP + LLM hybrid)

For **Discord** profiles we use a hybrid pipeline:

1. **NLP** (local, no API): vocabulary, sentiment, reactions, servers, network, topics.
2. **LLM** (local or cloud): psychological synthesis from NLP + samples → style, intimacy, hooks.

So even with a small local model, most of the “understanding” comes from deterministic NLP; the LLM only interprets and names it. That keeps quality reasonable and token use low.

## Recommended local models

- **Ollama**: `llama3.1:8b`, `mistral:7b`, `phi3` — good for synthesis and design prompts.
- **LM Studio**: load any GGUF; name the model `local-model` or set `LLM_MODEL`.
- **vLLM**: use for throughput and longer contexts (e.g. 8k+).

## Troubleshooting

- **Connection refused** — Start Ollama/LM Studio/vLLM first and confirm the URL/port.
- **Wrong model** — Pass `--model-name` or set `LLM_MODEL` to the exact name the server expects.
- **Slow** — Use a smaller model (e.g. `mistral:7b`) or more GPU RAM for larger models.
