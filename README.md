# Code Review Agent

> AI-powered, multi-dimensional code review for local directories and Git repositories.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

---

## Overview

**Code Review Agent** runs LLM-driven analysis over your codebase and produces a structured report covering six quality dimensions:

| Dimension | What it checks |
|-----------|---------------|
| 🔒 Security | Hardcoded secrets, injection risks, auth flaws |
| ✅ Correctness | Logic errors, null-safety, exception handling |
| ⚡ Performance | Bottlenecks, unnecessary allocations, I/O patterns |
| 📐 Code Style | Naming, formatting, language idioms |
| 🏗️ Best Practices | Design patterns, SOLID principles, test coverage signals |
| 🔧 Maintainability | Complexity, duplication, documentation gaps |

Reports are delivered as a **filterable HTML dashboard** or **machine-readable JSON**.

---

## Quick Install

**Prerequisites:** Python 3.11+, Git

### Online install

```bash
# 1. Clone
git clone https://github.com/your-org/code-review-agent.git
cd code-review-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your LLM provider
cp config/config.yaml.example config/config.yaml
# Edit config/config.yaml → set provider + API key (or use .env)
```

### Offline / air-gapped install

**Step 1 — on a machine with internet access, download all packages:**

```bash
pip download -r requirements.txt -d packages/
```

This saves every wheel/sdist into the `packages/` directory. Copy the entire project folder (including `packages/`) to the target machine.

**Step 2 — on the offline machine, install from the local cache:**

```bash
pip install --no-index --find-links=packages/ -r requirements.txt
```

> `packages/` is listed in `.gitignore` by default — commit it to your internal repo or distribute it as a tarball alongside the project.

A helper script `scripts/download_packages.sh` is provided for convenience:

```bash
bash scripts/download_packages.sh   # downloads packages/ on the current machine
```

**.env (recommended for secrets) — set the key and model for your chosen provider:**

```env
# DeepSeek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-coder       # optional, overrides config.yaml

# OpenAI
# OPENAI_API_KEY=sk-xxx
# OPENAI_MODEL=gpt-4o

# Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-xxx
# CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Ollama — no key required, local service
# OLLAMA_MODEL=codellama
```

---

## Getting Started

### Review a local directory

```bash
python run.py /path/to/your/project
```

### Review a remote Git repository

```bash
python run.py https://github.com/owner/repo --provider deepseek --format html
```

### Common options

| Option | Default | Description |
|--------|---------|-------------|
| `--provider` | `deepseek` | LLM provider — see table below |
| `--model` | *(config.yaml)* | Model name override |
| `--format` | `html` | Output format: `html` or `json` |
| `--output` | `./output` | Directory to write the report |

**Supported providers:**

| Provider | API Key env | Model env | Default model |
|----------|-------------|-----------|---------------|
| `deepseek` | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` | `deepseek-coder` |
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-4o` |
| `claude` | `ANTHROPIC_API_KEY` | `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` |
| `ollama` | *(none)* | `OLLAMA_MODEL` | `codellama` |

Model resolution order: **call argument → env var → config.yaml → built-in default**

The report is saved to `output/review_<timestamp>.html` (or `.json`).

---

## Documentation

### Configuration (`config/config.yaml`)

```yaml
provider: deepseek   # deepseek | openai | claude | ollama

deepseek:
  api_key: ${DEEPSEEK_API_KEY}
  model: deepseek-coder
  timeout: 300

openai:
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o
  timeout: 120

claude:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-3-5-sonnet-20241022
  timeout: 120

ollama:
  base_url: http://localhost:11434
  model: codellama

analyzer:
  max_chunk_lines: 150   # lines per review chunk
  concurrency: 2         # parallel LLM calls

ignore_dirs:
  - tests
  - migrations
```

All values support `${ENV_VAR:-default}` environment variable substitution.

### Deployment options

#### Option A — CLI (zero setup)

```bash
python run.py <source> --provider deepseek --format html
```

#### Option B — MCP HTTP service (Docker)

See the full **Build, Deploy & Test** guide below.

#### Option C — Claude Desktop / Claude Code (stdio MCP)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-review": {
      "command": "python",
      "args": ["/absolute/path/to/code-review-agent/mcp_server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-xxx",
        "DEEPSEEK_MODEL": "deepseek-coder"
      }
    }
  }
}
```

Set the API key and model env vars for your chosen provider. Examples for other providers:

```jsonc
// OpenAI
"env": { "OPENAI_API_KEY": "sk-xxx", "OPENAI_MODEL": "gpt-4o" }

// Anthropic Claude
"env": { "ANTHROPIC_API_KEY": "sk-ant-xxx", "CLAUDE_MODEL": "claude-3-5-sonnet-20241022" }

// Ollama (no key needed)
"env": { "OLLAMA_MODEL": "codellama" }
```

Available MCP tools:

| Tool | Description |
|------|-------------|
| `review_local_code` | Review a local path accessible to the server |
| `review_git_repo` | Clone + review a remote Git repository |
| `list_reports` | List recently generated reports |
| `get_report_content` | Read a JSON report by path |
| `list_providers` | Show supported providers and which keys are configured |

#### Option D — dodo SKILL

If you use the dodo AI assistant, install the bundled skill from `skill/SKILL.md`.
Trigger phrases: *"帮我做代码审查 /path/to/project"* or *"review my code at …"*

---

### Build, Deploy & Test

#### 1. Prepare `.env`

```env
# Pick one provider and fill in its key + model
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-coder

# OPENAI_API_KEY=sk-xxx
# OPENAI_MODEL=gpt-4o

# ANTHROPIC_API_KEY=sk-ant-xxx
# CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Ollama (local, no key)
# OLLAMA_MODEL=codellama

# Host directory to mount into the container (defaults to $HOME)
# REVIEW_SOURCE_DIR=/path/to/your/projects
```

#### 2. Build the image

**Online build** (pulls packages from PyPI):

```bash
docker build -t code-review-agent:latest .
```

**Offline build** (requires `packages/` pre-populated by `scripts/download_packages.sh`):

```bash
# On a networked machine first:
bash scripts/download_packages.sh

# Then on the target machine (packages/ already present):
docker build -t code-review-agent:latest .
# Dockerfile detects packages/ and installs without network access
```

#### 3. Deploy

**Using docker compose (recommended):**

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f code-review

# Restart after config change (no rebuild needed — config/ is mounted)
docker compose restart code-review

# Stop and remove container
docker compose down
```

**Using plain docker run:**

```bash
docker run -d \
  --name code-review-agent \
  -p 8080:8080 \
  -v "$HOME:/workspace:ro" \
  -v "$(pwd)/output:/app/output" \
  -v "$(pwd)/config:/app/config:ro" \
  --env-file .env \
  --restart unless-stopped \
  code-review-agent:latest
```

The MCP SSE endpoint is available at `http://localhost:8080`.
The container exposes your host filesystem under `/workspace` (read-only).

#### 4. Test

**Health check:**

```bash
curl http://localhost:8080/health
# expected: 200 OK
```

**Smoke test — review a local project via MCP:**

```bash
curl -s -X POST http://localhost:8080/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "review_local_code",
    "arguments": {
      "path": "/workspace/my-project",
      "provider": "deepseek",
      "output_format": "json"
    }
  }' | python3 -m json.tool
```

**Check which providers are configured:**

```bash
curl -s -X POST http://localhost:8080/call \
  -H "Content-Type: application/json" \
  -d '{"tool": "list_providers", "arguments": {}}' \
  | python3 -m json.tool
```

**Run without Docker (quick local test):**

```bash
# stdio mode — one-shot call
echo '{"tool":"list_providers","arguments":{}}' \
  | python mcp_server.py

# SSE mode — keep running, then curl from another terminal
python mcp_server.py --transport sse --port 8080
```

#### 5. Upgrade

```bash
# Pull latest code
git pull

# Rebuild image (dependencies layer is cached if requirements.txt unchanged)
docker compose build

# Rolling restart
docker compose up -d
```

1. Fork the repository and create a feature branch.
2. Write clear, focused commits — one logical change per commit.
3. Keep new code consistent with the existing async/await style.
4. Open a pull request with a description of what changed and why.

Issues and feature requests are welcome — please search existing issues before filing a new one.

---

## Community

- **Issues & feature requests:** GitHub Issues
- **Discussions:** GitHub Discussions

---

## License

Released under the [MIT License](LICENSE).