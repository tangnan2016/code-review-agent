# Code Review Agent

> AI-powered, multi-dimensional code review for local directories and Git repositories.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

---

## Overview

**Code Review Agent** runs LLM-driven analysis over your codebase and produces a structured report covering six quality dimensions:

| Dimension | What it checks |
|-----------|----------------|
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

# 3. Configure your LLM provider — copy the example and edit
cp env.example.txt .env
# Fill in your provider key and model (see Configuration section below)
```

### Offline / air-gapped install

**Step 1 — on a machine with internet access:**

```bash
bash scripts/download_packages.sh   # saves all wheels into packages/
```

**Step 2 — on the offline machine (copy the entire project folder including `packages/`):**

```bash
pip install --no-index --find-links=packages/ -r requirements.txt
```

> `packages/` is listed in `.gitignore` — commit it to your internal repo or distribute it as a tarball alongside the project.

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
| `--provider` | *(config.yaml)* | LLM provider — see table below |
| `--model` | *(config.yaml)* | Model name override |
| `--format` | `html` | Output format: `html` or `json` |
| `--output` | `./reports` | Directory to write the report |

The report is saved to `reports/review_<timestamp>.html` (or `.json`).

---

## Configuration

### LLM providers

| Provider | Provider-specific key env | Model env | Default model |
|----------|---------------------------|-----------|---------------|
| `deepseek` | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` | `deepseek-chat` |
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-4o` |
| `claude` | `ANTHROPIC_API_KEY` | `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` |
| `ollama` | *(none)* | `OLLAMA_MODEL` | `llama3` |
| *custom* | `LM_API_KEY` + `LM_BASE_URL` | `LLM_MODEL` | *(set via env)* |

**Custom / third-party providers** (e.g. Qwen, Moonshot, any OpenAI-compatible API) are supported without code changes — set `LM_PROVIDER`, `LM_API_KEY`, `LM_BASE_URL`, and `LLM_MODEL` in `.env`:

```env
LM_PROVIDER=qwen
LM_API_KEY=sk-xxx
LM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-plus
```

> **`base_url` must point to the API root** (e.g. `.../v1`), not the full endpoint path.
> If it accidentally ends with `/chat/completions`, the agent will log a warning and strip it automatically.

### `.env` file

Copy `env.example.txt` to `.env` and fill in the values for your chosen provider:

```env
# ── Switch active provider (overrides config.yaml) ──────────────────────────
# LM_PROVIDER=deepseek

# ── DeepSeek ─────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY=sk-xxx
# DEEPSEEK_MODEL=deepseek-chat        # optional override
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ── OpenAI ───────────────────────────────────────────────────────────────────
# OPENAI_API_KEY=sk-xxx
# OPENAI_MODEL=gpt-4o
# OPENAI_BASE_URL=https://api.openai.com/v1

# ── Anthropic Claude ─────────────────────────────────────────────────────────
# ANTHROPIC_API_KEY=sk-ant-xxx
# CLAUDE_MODEL=claude-3-5-sonnet-20241022

# ── Ollama (local, no key required) ──────────────────────────────────────────
# OLLAMA_MODEL=llama3
# OLLAMA_BASE_URL=http://localhost:11434

# ── Custom / third-party provider (OpenAI-compatible) ────────────────────────
# LM_PROVIDER=qwen
# LM_API_KEY=sk-xxx
# LM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# LLM_MODEL=qwen3.6-plus

# ── Analyzer tuning ──────────────────────────────────────────────────────────
# ANALYZER_CONCURRENCY=2        # parallel LLM calls (lower = less timeout risk)
# ANALYZER_MAX_CHUNK_LINES=300  # lines per review chunk
```

> **⚠️ Do NOT add `FASTMCP_HOST` / `FASTMCP_PORT` to `.env`**
> These variables have no effect in mcp v1.x. Host/port are passed directly to the `FastMCP()` constructor via CLI args. To change the binding, edit the `command:` in `docker-compose.yml`.

### Environment variable reference

**Priority order (high → low):** provider-specific env var → generic env var → `config.yaml`

#### Provider-specific

| Variable | Config path |
|----------|-------------|
| `DEEPSEEK_API_KEY` | `llm.providers.deepseek.api_key` |
| `DEEPSEEK_MODEL` | `llm.providers.deepseek.model` |
| `DEEPSEEK_BASE_URL` | `llm.providers.deepseek.base_url` |
| `OPENAI_API_KEY` | `llm.providers.openai.api_key` |
| `OPENAI_MODEL` | `llm.providers.openai.model` |
| `OPENAI_BASE_URL` | `llm.providers.openai.base_url` |
| `ANTHROPIC_API_KEY` | `llm.providers.claude.api_key` |
| `CLAUDE_MODEL` | `llm.providers.claude.model` |
| `CLAUDE_BASE_URL` | `llm.providers.claude.base_url` |
| `OLLAMA_MODEL` | `llm.providers.ollama.model` |
| `OLLAMA_BASE_URL` | `llm.providers.ollama.base_url` |

#### Generic (apply to the active provider — lower priority than provider-specific)

| Variable | Type | Config path |
|----------|------|-------------|
| `LM_PROVIDER` | string | `llm.default_provider` — switches active provider |
| `LM_API_KEY` | string | `llm.providers.<active>.api_key` |
| `LM_BASE_URL` | string | `llm.providers.<active>.base_url` |
| `LLM_MODEL` | string | `llm.providers.<active>.model` |
| `LLM_TEMPERATURE` | float | `llm.providers.<active>.temperature` |
| `LLM_MAX_TOKENS` | int | `llm.providers.<active>.max_tokens` |
| `LLM_TIMEOUT` | int (s) | `llm.providers.<active>.timeout` |

#### Analyzer

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ANALYZER_CONCURRENCY` | int | `2` | Parallel LLM calls |
| `ANALYZER_MAX_CHUNK_LINES` | int | `300` | Max lines per review chunk |

### `config.yaml` reference

```yaml
llm:
  default_provider: "deepseek"   # deepseek | openai | claude | ollama | <custom>
  providers:
    deepseek:
      api_key: "${DEEPSEEK_API_KEY}"
      model: "deepseek-chat"
      base_url: "https://api.deepseek.com/v1"
      temperature: 0.3
      max_tokens: 4096
      timeout: 300

    openai:
      api_key: "${OPENAI_API_KEY}"
      model: "gpt-4o"
      temperature: 0.3
      max_tokens: 4096
      timeout: 120

    claude:
      api_key: "${ANTHROPIC_API_KEY}"
      model: "claude-3-5-sonnet-20241022"
      temperature: 0.3
      max_tokens: 4096
      timeout: 120

    ollama:
      model: "llama3"
      base_url: "http://localhost:11434"
      temperature: 0.3
      max_tokens: 4096
      timeout: 120

analyzer:
  concurrency: 2           # parallel LLM calls; lower value reduces timeout risk
  max_chunk_lines: 300     # lines per review chunk
  overlap_lines: 20        # overlap between consecutive chunks (preserves context)

report:
  output_dir: "./reports"
  format: "html"           # html | json
```

All `config.yaml` values support `${VAR}` and `${VAR:-default}` environment variable substitution.

---

## Deployment Options

### Option A — CLI (zero setup)

```bash
python run.py /path/to/project --format html
```

### Option B — MCP HTTP service (Docker)

See the full **Build, Deploy & Test** section below.

### Option C — Claude Desktop / Claude Code (stdio MCP)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-review": {
      "command": "python",
      "args": ["/absolute/path/to/code-review-agent/mcp_server.py"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-xxx",
        "DEEPSEEK_MODEL": "deepseek-chat"
      }
    }
  }
}
```

For other providers, change the `env` block accordingly:

```jsonc
// OpenAI
"env": { "OPENAI_API_KEY": "sk-xxx", "OPENAI_MODEL": "gpt-4o" }

// Anthropic Claude
"env": { "ANTHROPIC_API_KEY": "sk-ant-xxx", "CLAUDE_MODEL": "claude-3-5-sonnet-20241022" }

// Custom provider (e.g. Qwen)
"env": {
  "LM_PROVIDER": "qwen",
  "LM_API_KEY": "sk-xxx",
  "LM_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "LLM_MODEL": "qwen3.6-plus"
}
```

### Option D — dodo SKILL

If you use the dodo AI assistant, install the bundled skill from `skill/SKILL.md`.
Trigger phrases: *"review my code at /path/to/project"* or *"help me do a code review at …"*

---

## Build, Deploy & Test

### 1. Build the Docker image

**Online build** (pulls packages from PyPI):

```bash
docker build -t code-review-agent:latest .
```

**Offline build** (requires `packages/` pre-populated):

```bash
# On a networked machine:
bash scripts/download_packages.sh

# On the target machine (packages/ already present):
docker build -t code-review-agent:latest .
```

### 2. Deploy

**Using docker compose (recommended):**

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f code-review

# Restart after config change (no rebuild needed — config/ is volume-mounted)
docker compose restart code-review

# Stop and remove
docker compose down
```

**Using plain `docker run`:**

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
Your host filesystem is mounted read-only under `/workspace` inside the container.

To change the bind address or port, edit `docker-compose.yml`:

```yaml
command: ["--transport", "sse", "--host", "0.0.0.0", "--port", "8080"]
```

### 3. Test

> **MCP SSE is not a REST API** — there are no `/call` or `/health` routes.
> The protocol is JSON-RPC 2.0 over SSE. You must open `/sse` to obtain a `session_id`, complete the initialization handshake, and then POST requests to `/messages/`.
> Using **MCP Inspector** is strongly recommended for interactive testing.

---

#### Option A — MCP Inspector (recommended, visual UI)

```bash
# Launch Inspector — prints a pre-filled browser URL with auth token
npx @modelcontextprotocol/inspector

# Or disable token auth for local dev/test
DANGEROUSLY_OMIT_AUTH=true npx @modelcontextprotocol/inspector
```

Terminal output after launch:

```
⚙️  Proxy server listening on 127.0.0.1:6277
🔗 Open inspector with token pre-filled:
    http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=<token>
```

Open the link in your browser (port `6274`), then:

1. Set **Transport** to `SSE`, set **URL** to `http://localhost:8080/sse`, click **Connect**
2. **⚠️ Increase the request timeout** — find **"Request Timeout (ms)"** in the left panel and set it to `300000` (5 minutes).
   The default is ~10 s; reviewing a 20+ file project will fail with `MCP error -32001: Request timed out` otherwise.
3. Click **Tools** in the left panel → select a tool → fill in arguments → **Run Tool**

---

#### Option B — stdio one-liner (fastest sanity check)

```bash
export DEEPSEEK_API_KEY=sk-xxx

# List all tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python mcp_server.py

# Call list_providers
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_providers","arguments":{}}}' \
  | python mcp_server.py
```

---

#### Option C — SSE curl (two-terminal, suitable for integration testing)

MCP SSE requires two concurrent connections and a **3-step handshake** before calling any tool.

```bash
# Terminal A: open SSE stream and keep it running — do NOT press Ctrl+C
curl -N http://localhost:8080/sse
# Expected output:
# event: endpoint
# data: /messages/?session_id=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```bash
# Terminal B: send the following requests in order
# Replace SESSION with the session_id value from Terminal A
SESSION=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
HOST=http://localhost:8080

# Step 1 — initialize (must be the very first message)
curl -s -X POST "$HOST/messages/?session_id=$SESSION" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "curl-test", "version": "0.1"}
    }
  }'

# Step 2 — notifications/initialized (no "id" field — this is a notification)
curl -s -X POST "$HOST/messages/?session_id=$SESSION" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}'

# Step 3 — now call tools normally

# List all tools
curl -s -X POST "$HOST/messages/?session_id=$SESSION" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'

# Call list_providers
curl -s -X POST "$HOST/messages/?session_id=$SESSION" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
       "params": {"name": "list_providers", "arguments": {}}}'

# Call review_local_code (use the in-container path under /workspace)
curl -s -X POST "$HOST/messages/?session_id=$SESSION" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 4, "method": "tools/call",
    "params": {
      "name": "review_local_code",
      "arguments": {
        "path": "/workspace/my-project",
        "provider": "deepseek",
        "output_format": "json"
      }
    }
  }'
```

**Important notes:**
- All POSTs return `202 Accepted` with an **empty body** — this is correct. The actual JSON-RPC response is pushed back through the SSE stream in Terminal A.
- Skipping the `initialize` step returns `-32602 Invalid request parameters`.
- Use the **in-container path** (`/workspace/my-project`), not the host path (`/Users/xxx/...`).
- If `review_local_code` times out in MCP Inspector (`-32001`), increase the request timeout to `300000 ms`.

### 4. Verify LLM connectivity (curl)

Before running a full review, quickly verify that your LLM provider is reachable and the API key is valid:

```bash
# Replace BASE_URL and API_KEY with the values from your .env
curl -s -X POST "<BASE_URL>/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_KEY>" \
  -d '{
    "model": "<MODEL>",
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "max_tokens": 50
  }' | python3 -m json.tool
```

Expected: HTTP `200` with a non-empty `choices[0].message.content`.
If the call takes > 30 s on this short prompt, the API endpoint or key has an issue unrelated to this agent.

### 5. Upgrade

```bash
git pull
docker compose build   # dependency layer is cached if requirements.txt unchanged
docker compose up -d
```

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `review_local_code` | Review a local path accessible to the server |
| `review_git_repo` | Clone and review a remote Git repository |
| `list_reports` | List recently generated reports |
| `get_report_content` | Read a JSON report by path |
| `list_providers` | Show supported providers and which keys are configured |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Container binds to `127.0.0.1:8000` instead of `0.0.0.0:8080` | `FASTMCP_HOST`/`FASTMCP_PORT` env vars have no effect in mcp v1.x | Pass `--host 0.0.0.0 --port 8080` via `docker run` args or `docker-compose.yml` `command:` |
| `unrecognized arguments: python mcp_server.py` on `docker run` | `ENTRYPOINT` already includes `python mcp_server.py`; don't repeat it | Run: `docker run ... image --transport sse` (args only, no command prefix) |
| `ClosedResourceError` on POST | SSE connection was closed (Ctrl+C) before POST | Keep Terminal A (SSE stream) open while sending POSTs from Terminal B |
| `-32602 Invalid request parameters` | Skipped MCP handshake | Send `initialize` → `notifications/initialized` before any tool call |
| `FileNotFoundError: path does not exist: /Users/xxx/...` | Host path passed to container | Mount host dir with `-v /host/path:/workspace:ro`, use `/workspace/...` in the tool call |
| `-32001 Request timed out` (MCP Inspector) | Default timeout is ~10 s | Set "Request Timeout (ms)" to `300000` in the Inspector left panel |
| `SocketTimeoutError: Timeout on reading data from socket` | LLM API slow to respond (complex prompt, high load) | Agent retries automatically with backoff; or lower `ANALYZER_CONCURRENCY=1` in `.env` |
| `401 Authentication Fails` | API key invalid or expired | Renew the key; verify the correct env var is set for your provider |
| `LLM shows wrong provider name` (e.g. `deepseek` instead of `qwen`) | `load_dotenv()` not called / priority bug in env var override | Ensure `config_loader.py` is up to date; `.env` loads with `load_dotenv(override=False)` |
| `URL becomes .../chat/completions/chat/completions` | `base_url` includes endpoint path | Set `base_url` to the API root only (e.g. `https://api.example.com/v1`); agent auto-strips the suffix and logs a warning |

---

## Contributing

1. Fork the repository and create a feature branch.
2. Write clear, focused commits — one logical change per commit.
3. Keep new code consistent with the existing `async`/`await` style.
4. Open a pull request describing what changed and why.

Issues and feature requests are welcome — please search existing issues before filing a new one.

---

## License

Released under the [MIT License](LICENSE).