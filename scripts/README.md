# Workbench Scripts

This directory contains scripts for generating LLM nodes and synchronizing shared assets across the Workbench monorepo.

## Scripts

### generate_llm_nodes.js
Generates LLM node definitions by fetching available models from OpenRouter. Creates config, JavaScript process, Python process, and test files for each model.

### generate_embedding_nodes.js / generate_rerank_nodes.js
Generate embedding and rerank nodes from OpenRouter's `embeddings` and `rerank` output modalities.

### generate_decision_nodes.js
Generates `decision` nodes for System One models (OpenRouter's `decisions` output modality, e.g. TypeSafe Jev). These are not chat models: each node takes a `state` and a map of typed `questions` (`noul`, `choice`, `score`) and returns typed `answers` via OpenRouter's `/systemone` endpoint. Per-provider restrictions go in `decision-generator.config.json` under `provider_overrides`.

All generators skip OpenRouter `:batch` model variants, which only work through the asynchronous batch API.

### sync_sdks.py
Python script for one-time synchronization of nodes, types, and test flows to all SDKs.

### sync-watcher.js
A Node.js file watcher that automatically syncs changes from the `/nodes`, `/types`, and `/tests` directories to language-specific SDKs in real-time.

## Installation

```bash
cd scripts
npm install
```

## LLM Node Generation

Generate or update LLM nodes from OpenRouter's model catalog:

```bash
# Requires OPENROUTER_API_KEY in .env or environment
cd scripts
node generate_llm_nodes.js

# Dry run (preview changes without writing files)
node generate_llm_nodes.js --dry-run

# Then sync to SDKs
python sync_sdks.py
```

### Configuration

Edit `generator.config.json` to control which providers/models are generated:

```json
{
  "providers": {
    "anthropic": { "enabled": true },
    "openai": { "enabled": true }
  },
  "generation": {
    "dry_run": false,
    "include_python": true
  },
  "output": {
    "cleanup_old_nodes": true
  }
}
```

See `generator.config.example.json` for all available options.

Router models (e.g. `typesafe/jev-router`, listed by OpenRouter with pricing `-1`) are generated as chat nodes with variable pricing. OpenRouter lists no supported parameters for routers, so declare the ones they accept under `model_overrides`:

```json
{
  "model_overrides": {
    "typesafe/jev-router": {
      "supported_parameters": ["tools", "tool_choice", "temperature", "max_tokens", "include_reasoning"]
    }
  }
}
```

### Regenerating everything

```bash
cd scripts
node generate_llm_nodes.js
node generate_embedding_nodes.js
node generate_rerank_nodes.js
node generate_decision_nodes.js
python sync_sdks.py
```

## Usage

### One-time sync
```bash
npm run sync
# or
node sync-watcher.js
```

### Watch mode (auto-sync on changes)
```bash
npm run watch
# or
node sync-watcher.js --watch
```

### Development mode (watch with verbose logging)
```bash
npm run dev
# or
node sync-watcher.js --watch --verbose
```

## Features

- **Real-time watching**: Automatically detects file changes in `/nodes`, `/types`, and `/tests` directories
- **Selective copying**: Only copies files with extensions relevant to each SDK (e.g., `.js`/`.ts` for Node.js)
- **Master config generation**: Creates `all-nodes.config.json` and `all-nodes-simple.config.json`
- **Verbose logging**: Optional detailed logging for debugging
- **Graceful shutdown**: Handles Ctrl+C properly

## Development Workflow

1. Start the watcher in development mode:
   ```bash
   npm run dev
   ```

2. Make changes to files in `/nodes`, `/types`, or `/tests` directories

3. The watcher will automatically copy relevant files to the appropriate SDK directories

4. Press Ctrl+C to stop the watcher

## Supported SDKs

Currently supports:
- **Node.js** (`.js`, `.ts` files)

Future SDKs can be easily added by updating the `SDK_TARGETS` configuration in `sync-watcher.js`.
