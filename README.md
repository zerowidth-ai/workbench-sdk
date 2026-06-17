# Workbench - Collaborative AI Design & Orchestration

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Node.js SDK](https://img.shields.io/npm/v/@zerowidth/workbench-sdk?label=Node.js%20SDK)](https://www.npmjs.com/package/@zerowidth/workbench-sdk)

> **🎨 Design the AI that powers your products collaboratively at [zerowidth.ai](https://zerowidth.ai) and bring it to production with our open-source SDKs**

Welcome to the Workbench open-source monorepo! This repository contains the execution engines, node libraries, and tools that power ZeroWidth's collaborative AI design platform. Think Figma for AI - design, align on, and orchestrate the AI behaviors that will power your next-generation products and services at [zerowidth.ai](https://zerowidth.ai), then execute them anywhere via our API, using these open-source SDKs, or by having Workbench act as the design spec for any framework of choice.

## 🎯 What is Workbench?

Workbench is a collaborative platform for designing and aligning on AI behavior before production. Rather than another workflow automation tool, Workbench enables teams to work together in shared workspaces to design, test, and refine the AI orchestrations that will become the intelligent core of their products and services. Create custom collections of prompt libraries, evaluators, and specialized agents - all nestable and configurable without code.

### Key Features

- **👥 Collaborative Workspaces**: Teams design AI behavior together in shared environments
- **🎨 Visual AI Design**: Intuitive drag-and-drop interface for complex AI orchestrations
- **🤖 180+ AI Models**: Native support for OpenAI, Anthropic, Google, Mistral, DeepSeek, and more
- **📚 Design Systems for AI**: Custom collections, prompt libraries, nestable agents, and reusable components
- **🔬 Built-in Evaluation**: Test and validate AI behavior before production deployment
- **🚀 Production Ready**: Deploy via API/SDK or use as design specs for any framework
- **🔐 Secure by Design**: API keys and sensitive data stay in your environment
- **📊 Full Observability**: Monitor costs, performance, and AI behavior in real-time

## 🗂️ Repository Structure

This monorepo is organized to support multiple programming languages while sharing common node definitions and types:

```
workbench-sdk/
├── README.md                    # This file
├── LICENSE                      # MIT License
├── nodes/                       # 🎯 200+ shared node definitions
│   ├── add/                     # Math: Addition operations
│   ├── anthropic-claude-3-5-sonnet/ # AI: Claude 3.5 Sonnet model
│   ├── array-map/               # Data: Array transformation
│   ├── csv-parser/              # Data: CSV file processing
│   ├── http-request/            # Network: HTTP API calls
│   ├── if-else/                 # Logic: Conditional branching
│   ├── input-data/              # I/O: Data input nodes
│   └── ...                      # And 190+ more!
├── types/                       # 📝 Shared type definitions
│   ├── content.json             # Content type schemas
│   └── ...
├── sdks/                        # 🚀 Language-specific execution engines
│   ├── nodejs/                  # Node.js SDK
│   └── ...                      # Python, C#, Go (coming soon)
└── scripts/
    └── sync_sdks.py            # 🔄 Sync shared assets to SDKs
```

### Core Components

#### 🎯 Nodes (`/nodes`)
The building blocks of AI orchestration. Each node is a self-contained component for designing intelligent systems:

- **AI Models**: 180+ LLM integrations (OpenAI, Anthropic, Google, Mistral, DeepSeek, etc.)
- **Prompt Engineering**: Dynamic prompts, templates, and context management
- **Data Processing**: Arrays, strings, JSON, CSV, mathematical operations
- **I/O Operations**: Input/output handling, file operations, HTTP requests
- **Logic & Control**: Conditionals, loops, error handling, testing utilities
- **Evaluation & Testing**: Model comparison, quality scoring, A/B testing

#### 📝 Types (`/types`)
Shared type definitions and schemas that ensure consistency across all SDKs.

#### 🚀 SDKs (`/sdks`)
Language-specific execution engines that interpret and run Workbench AI orchestrations:

- **Node.js** (`/sdks/nodejs`) - ✅ Available now
- **Python** - 🚧 Coming soon
- **C#** - 🚧 Coming soon  
- **Go** - 🚧 Coming soon

## 🚀 Quick Start

### 1. Design Your AI Orchestration
Visit [zerowidth.ai](https://zerowidth.ai) to collaborate on AI design with your team:

1. **Sign up** at [zerowidth.ai](https://zerowidth.ai) (free tier available)
2. **Create workspaces** for your team and projects
3. **Build collections** of prompts, agents, and evaluators
4. **Design AI flows** using drag-and-drop visual interface
5. **Test & evaluate** AI behavior with built-in tools
6. **Export** your orchestration as a `.zwf` file (the current Workbench flow format) or use via API

### 2. Execute Locally

#### Node.js
```bash
npm install @zerowidth/workbench-sdk
```

```javascript
import Workbench from '@zerowidth/workbench-sdk';

// Load your AI orchestration designed at zerowidth.ai
const engine = await Workbench.create('./myflow.zwf', {
  keys: {
    openrouter: process.env.OPENROUTER_API_KEY
  }
});

// Execute your AI behavior in production
const result = await engine.run({
  chat: [{ role: 'user', content: 'Hello, world!' }]
});

console.log(result.outputs);
```

For complete documentation, see the [Node.js SDK README](sdks/nodejs/README.md).

## 🎨 Example AI Orchestrations

### Simple AI Agent
```json
{
  "nodes": [
    {
      "id": "input1",
      "type": "input-chat",
      "settings": { "key": "messages" }
    },
    {
      "id": "ai1", 
      "type": "anthropic-claude-3-5-sonnet",
      "settings": { "system_prompt": "You are a helpful assistant." }
    },
    {
      "id": "output1",
      "type": "output-chat"
    }
  ],
  "links": [
    { "from": { "node_id": "input1", "port_name": "messages" },
      "to": { "node_id": "ai1", "port_name": "messages" } },
    { "from": { "node_id": "ai1", "port_name": "response" },
      "to": { "node_id": "output1", "port_name": "messages" } }
  ]
}
```

### Data Processing Pipeline
```json
{
  "nodes": [
    {
      "id": "csv1",
      "type": "csv-parser",
      "settings": { "has_headers": true }
    },
    {
      "id": "filter1",
      "type": "array-filter",
      "settings": { "condition": "item.age > 18" }
    },
    {
      "id": "api1",
      "type": "http-request", 
      "settings": { "method": "POST", "url": "https://api.example.com/process" }
    }
  ]
}
```

## 🛠️ Development & Contributing

### Setting Up Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/zerowidth-ai/workbench-sdk.git
   cd workbench-sdk
   ```

2. **Sync shared assets** (only needed for development)
   ```bash
   python scripts/sync_sdks.py
   ```
   This copies the shared `/nodes` and `/types` directories to each SDK.

3. **Work on specific SDKs**
   ```bash
   cd sdks/nodejs
   npm install
   npm test
   ```

### Repository Architecture

The monorepo uses a **shared core, distributed execution** model:

- **Shared Assets**: Node definitions and type schemas in `/nodes` and `/types`
- **Sync Script**: `sync_sdks.py` distributes shared assets to language-specific SDKs
- **Independent SDKs**: Each SDK can be developed, tested, and released independently
- **Consistent API**: All SDKs implement the same core execution interface

### Adding New Nodes

1. Create node directory in `/nodes/your-node-name/`
2. Add configuration: `your-node-name.config.json`
3. Implement processing logic in target languages:
   - `your-node-name.js` (Node.js)
   - `your-node-name.py` (Python - coming soon)
4. Add tests: `your-node-name.tests.json`
5. Sync to SDKs using one of these methods:

   **Option A: One-time sync**
   ```bash
   python scripts/sync_sdks.py
   ```

   **Option B: Auto-sync during development (recommended)**
   ```bash
   cd scripts
   npm install
   npm run dev  # Watches for changes and auto-syncs
   ```

   The auto-sync watcher monitors `/nodes`, `/types`, and `/tests` directories and automatically copies relevant files to language-specific SDKs in real-time.

## 🗺️ Roadmap

### SDKs
- [x] **Node.js/TypeScript** - Production ready
- [ ] **Python** - Coming soon
- [ ] **C#/.NET** - Coming soon
- [ ] **Go** - Coming soon
- [ ] **Rust** - Under consideration

### Platform Features
- [x] **Enterprise Collections** - Specialized AI components for enterprise systems
- [x] **AI Design Marketplace** - Community-contributed orchestrations and components
- [ ] **Local AI Designer** - Standalone desktop app for offline AI orchestration design
- [ ] **Advanced Evaluation** - A/B testing, model comparison, and quality scoring tools

### Integration Ecosystem
- [ ] **More AI Models** - Expanding beyond 180+ current LLM providers
- [ ] **Database Connectors** - Direct database integration components
- [ ] **Design System Sync** - Integration with existing design and development workflows

## 🔗 Getting Started

1. **🎨 Design**: Collaborate on AI orchestrations at [zerowidth.ai](https://zerowidth.ai)
2. **📖 Learn**: Read the [Node.js SDK documentation](sdks/nodejs/README.md)
3. **🚀 Deploy**: Bring your AI designs to production with our SDKs
4. **🤝 Contribute**: Help us build the future of collaborative AI design

## 📚 Resources

- **Platform**: [zerowidth.ai](https://zerowidth.ai) - Collaborative AI design platform
- **Documentation**: [zerowidth.ai/docs](https://zerowidth.ai/docs) - Comprehensive guides
- **Examples**: [zerowidth.ai/examples](https://zerowidth.ai/examples) - Sample AI orchestrations
- **Community**: [Discord](https://discord.gg/zerowidth) - Join our community
- **Support**: [support@zerowidth.ai](mailto:support@zerowidth.ai) - Get help

## 🤝 Contributing

We welcome contributions! Whether you're:

- 🐛 **Fixing bugs** in existing nodes or SDKs
- ✨ **Adding new features** or node types  
- 📖 **Improving documentation** and examples
- 🧪 **Writing tests** to improve reliability
- 💡 **Suggesting enhancements** for the platform

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏢 About ZeroWidth

ZeroWidth is: 

- **People** to provide insight, context, strategy, and advice on how your organization can meaningfully, productively integrate AI into your business.

- **Tools** to provide your organization with a suite of flexible, customizable ways for multiple disciplines and departments to collaborate on the design of AI seamlessly.

**Founded**: 2023   
**Headquarters**: Remote, US
**Website**: [zerowidth.ai](https://zerowidth.ai)

---

**Ready to design the AI that powers your products?** [Start collaborating at zerowidth.ai →](https://zerowidth.ai)