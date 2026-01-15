# CLAUDE.md - zv1 Project Guide

This file provides context for Claude Code when working with the zv1 codebase.

## Project Overview

zv1 is ZeroWidth's open-source AI orchestration framework. Users design flows visually at zv1.ai, export as `.zv1` files, and execute them locally using language-specific SDKs.

**Architecture**: Monorepo with shared node definitions and type schemas distributed to language-specific execution engines.

## Repository Structure

```
zv1/
├── nodes/                    # 200+ shared node definitions (synced to SDKs)
│   └── <node-name>/
│       ├── <node-name>.config.json    # Node schema and metadata
│       ├── <node-name>.process.js     # Node.js implementation
│       ├── <node-name>.process.py     # Python implementation
│       └── <node-name>.tests.json     # Test cases
├── types/                    # Shared type definitions (synced to SDKs)
├── tests/                    # Shared flow test files
│   └── flows/                # .zv1 and .json test flows
├── sdks/
│   ├── nodejs/               # Node.js SDK (production ready)
│   │   └── src/index.js      # Main engine implementation
│   └── python/               # Python SDK (in development)
│       └── src/              # Main engine implementation
├── scripts/
│   └── sync_sdks.py          # Distributes nodes/types/tests to SDKs
├── NODE_GUIDELINES.md        # Comprehensive node development guide
└── README.md                 # Project overview
```

## Key Commands

```bash
# Sync shared assets (nodes, types, tests) to all SDKs
python scripts/sync_sdks.py

# Auto-sync during development (watches for changes)
cd scripts && npm run dev

# Node.js SDK
cd sdks/nodejs
npm install
npm test                              # Run all tests
node tests/test.flows.js              # Run flow tests
node tests/test.flows.js flow.addition.zv1  # Run single flow test
node tests/test.all-nodes.js          # Run node unit tests
node tests/test.all-nodes.js --node add  # Run specific node test

# Python SDK
cd sdks/python
pip install -e .
python tests/test_flows.py            # Run flow tests
python tests/test_flows.py flow.addition.zv1  # Run single flow test
```

## Development Patterns

### Node Process Function Signatures

**Node.js** (`<node>.process.js`):
```javascript
export default async ({inputs, settings, config, nodeConfig}) => {
  return { output_field: value };
};
```

**Python** (`<node>.process.py`):
```python
async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    return {"output_field": value}
```

### Naming Conventions

- **Directories/files**: kebab-case (`my-node-name`)
- **Input/output/setting names**: snake_case (`total_results`)
- **Display names**: Title Case (`Total Results`)
- **Node types**: Same as directory name

### Error Handling

- Let errors bubble up - don't catch and return as output
- Throw descriptive, actionable error messages
- Don't include success/status/error fields in outputs

### Flow Test Formats

1. **Legacy JSON** (embedded flow): `flow.name.json` with `{"flow": {...}, "inputs": {...}, "expected": {...}}`
2. **New .zv1 format** (separate metadata): `flow.name.zv1` + `flow.name.test.json` with `{"inputs": {...}, "expected": {...}}`

## Key Files to Know

| File | Purpose |
|------|---------|
| `NODE_GUIDELINES.md` | Comprehensive node development standards |
| `scripts/sync_sdks.py` | Syncs nodes/types/tests to SDKs |
| `sdks/nodejs/src/index.js` | Main Node.js engine (reference implementation) |
| `sdks/python/src/__init__.py` | Main Python engine |
| `sdks/*/tests/test.flows.js` or `test_flows.py` | Flow integration tests |

## Node Categories

- **ai**: LLMs, embeddings (e.g., `anthropic-claude-3-5-sonnet`)
- **data**: Processing, transformation (e.g., `csv-parser`, `array-map`)
- **logic**: Conditionals, control flow (e.g., `if-else`)
- **io**: Input/output (e.g., `input-data`, `output-data`)
- **third-party**: External APIs (e.g., `http-request`)
- **testing**: Test utilities (e.g., `throw-error`, `null-bomb`)
- **macro**: Composite nodes with internal flows

## SDK Development Notes

### Node.js SDK

- Production ready
- Uses event-based signaling for node completion (P2 fix)
- Main class: `Zv1` in `src/index.js`
- Cache system in `src/utilities/cache.js`

### Python SDK

- In active development
- Requires Python 3.9+ (use `Union[]` not `|` for type hints)
- Uses keyword-only arguments (`*`) in process functions
- Main class: `Zv1` in `src/__init__.py`

### .NET SDK

- Early development (scaffolded, not yet tested)
- Requires .NET 8.0+
- Uses `NodeProcessorRegistry` pattern for node implementations
- See `sdks/dotnet/DEVELOPMENT_STATUS.md` for detailed status
- Basic nodes implemented: `add`, `input-data`, `output-data`
- Needs someone with .NET environment to build and test

## Common Workflows

### Adding a New Node

1. Create directory: `nodes/my-node/`
2. Add config: `my-node.config.json`
3. Implement JS: `my-node.process.js`
4. Implement Python: `my-node.process.py`
5. Add tests: `my-node.tests.json`
6. Run sync: `python scripts/sync_sdks.py`

### Running Tests After Changes

```bash
# After modifying Node.js engine
cd sdks/nodejs && npm test

# After modifying Python engine
cd sdks/python && python tests/test_flows.py

# After modifying a node
python scripts/sync_sdks.py
cd sdks/nodejs && node tests/test.all-nodes.js --node my-node
```

### Debugging Flow Execution

Enable debug mode in engine config:
```javascript
const engine = await zv1.create(flow, { debug: true });
```

```python
engine = await Zv1.create(flow, {"debug": True})
```

## Important Considerations

- Always sync SDKs after modifying nodes/types (`python scripts/sync_sdks.py`)
- Python nodes use keyword-only arguments - don't use positional args
- Flow tests live in `tests/flows/` and are synced to each SDK's `tests/flows/`
- Keep node implementations simple - avoid over-engineering
- Check `NODE_GUIDELINES.md` for detailed standards before adding nodes
