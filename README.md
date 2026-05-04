# humanize-mcp

> Made by Oliver Rochford · Aunoo AI

MCP server that exposes the humanize pipeline — heuristic AI-tells detection,
optional Ollama-backed deep scan, and AI rewrite — to any MCP client (Claude
Desktop, Claude Code, Cursor, Cline, custom agents).

Extracted from the `socmedia/`, `humanize/`, and `humanize-checker/` codebases
so the same capability is available without each consumer reimplementing the
detector or pinning a single LLM provider.

## Tools exposed

| Tool | LLM? | What it does |
|---|---|---|
| `detect_ai_tells(text)` | no | Run 31 regex/heuristic detectors, return tells + readability stats |
| `compute_readability(text)` | no | Word/sentence counts, Flesch, vocab diversity, em-dash count, bold count |
| `deep_scan(text)` | local SLM | Ollama-backed: inflated symbolism, faux-insightful voice, rhetorical escalation |
| `classify_verdict(text)` | local SLM | Heuristic evidence → AI/human verdict via Ollama |
| `build_humanize_prompt(text, ...)` | no | Returns `{system_prompt, user_prompt}` so the calling LLM can do the rewrite itself — no provider, no API key |
| `humanize_text(text, ..., dry_run=False)` | provider (or no, if `dry_run=True`) | Full rewrite. With `dry_run=True` returns prompts only, same as `build_humanize_prompt` |
| `list_presets` / `get_preset` / `create_preset` / `update_preset` / `delete_preset` | no | JSON-backed tone preset CRUD |
| `list_providers` | no | Which providers are configured right now |

### Self-rewrite mode (no provider needed)

If the calling agent IS an LLM (Claude in Claude Desktop / Code, etc.) and you'd
rather it produce the rewrite itself than spend a second API call, use
`build_humanize_prompt` (or `humanize_text(..., dry_run=True)`). The tool returns
the system + user prompt; the agent reads them and writes the rewritten text in
its next turn. Then call `detect_ai_tells` and `compute_readability` on the
result for before/after stats. No provider credentials required for this path.

## Install

```bash
cd /home/orochford/humanize-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

For tests: `pip install -e .[dev]`.

## Configuration

All config is via env vars. See `.env.example` for the full list.

```bash
HUMANIZE_DEFAULT_PROVIDER=anthropic   # anthropic | openai | bedrock
HUMANIZE_DEFAULT_MODEL=               # blank → provider default
HUMANIZE_PRESETS_PATH=~/.humanize-mcp/presets.json
HUMANIZE_OLLAMA_URL=                  # blank → deep_scan returns {available: false}
HUMANIZE_OLLAMA_MODEL=gemma3:4b

ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
AWS_REGION=us-east-1   # boto3 picks up the standard credential chain
```

Per-call `provider=...` and `model=...` arguments override the defaults.

### Provider defaults

| Provider | Default model |
|---|---|
| anthropic | `claude-sonnet-4-6` |
| openai | `gpt-4.1` |
| bedrock | `us.amazon.nova-pro-v1:0` |

OpenAI o-series models skip the `temperature` parameter automatically; GPT-5 /
o-series use `max_completion_tokens` instead of `max_tokens` (parity with the
existing `humanize/backend/llm.py`).

## Running

Standalone smoke test:

```bash
python -m humanize_mcp.server
```

The server speaks MCP over stdio — it stays connected to the parent process
and reads/writes JSON-RPC frames.

### Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "humanize": {
      "command": "/absolute/path/to/humanize-mcp/.venv/bin/python",
      "args": ["-m", "humanize_mcp.server"],
      "env": {
        "HUMANIZE_DEFAULT_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Restart Claude Desktop. The `humanize` tools should appear in the tool picker.

### Claude Code

```bash
claude mcp add humanize -- /absolute/path/to/humanize-mcp/.venv/bin/python -m humanize_mcp.server
```

Or edit `.claude/mcp.json` in the project / `~/.claude/mcp.json` for the user
scope. Pass env vars with `--env KEY=VALUE`.

### Cursor / Cline / other clients

Same pattern — point the client at the `humanize-mcp` console script (or
`python -m humanize_mcp.server`) and supply env vars.

## Usage walkthrough

### A. Calling LLM does the rewrite (no API key, no second model)

The natural flow when the MCP client is itself an LLM (Claude Desktop / Code,
Cursor, etc.). The agent calls three tools across two turns:

```
1. agent → detect_ai_tells({"text": "<draft>"})
   ← {tells: [...], stats: {...}}        # see what's wrong

2. agent → build_humanize_prompt({"text": "<draft>", "tone": "casual",
                                   "length_mode": "concise"})
   ← {system_prompt, user_prompt,
      tells_before, stats_before,
      instructions_for_caller}

3. agent reads system_prompt + user_prompt and writes the rewritten text
   itself in its next message — no extra API call.

4. (optional) agent → detect_ai_tells({"text": "<rewritten>"})
                      compute_readability({"text": "<rewritten>"})
   ← compare with tells_before / stats_before
```

`humanize_text(..., dry_run=True)` is equivalent to step 2.

### B. Server does the rewrite via a configured provider

For non-LLM agents, or when you want to pin a specific model (e.g. Bedrock
Nova Pro for parity with the socmedia app):

```
agent → humanize_text({"text": "<draft>", "provider": "anthropic",
                       "model": "claude-sonnet-4-6", "tone": "casual"})
     ← {original, rewritten, provider, model, latency_ms, tokens,
        stats_before, stats_after, tells_before, tells_after}
```

Provider falls back to `HUMANIZE_DEFAULT_PROVIDER` when omitted; model falls
back to the provider's default (see table above).

### C. Tone presets

```
1. create_preset({"name": "Punchy blog", "tone": "casual",
                  "length_mode": "concise", "paragraph_style": "prose",
                  "instructions": "Cut filler aggressively. Use contractions."})
   ← {id: "abc123def456", name: "Punchy blog", ...}

2. humanize_text({"text": "<draft>", "preset_id": "abc123def456"})
   # preset values fill in for any args left at their defaults
```

`list_presets` enumerates them; `update_preset` / `delete_preset` mutate.

### D. Local SLM deep scan (optional)

Requires Ollama running with `gemma3:4b` pulled and `HUMANIZE_OLLAMA_URL` set:

```
deep_scan({"text": "<draft>"})
  ← {available: true, findings: [
      {tell_type: "inflated_symbolism", text: "...", suggestion: "..."},
      ...
    ]}

classify_verdict({"text": "<draft>"})
  ← {available: true, verdict: "likely AI", confidence: "medium", reason: "..."}
```

Without Ollama, both return `{available: false, reason: "..."}` cleanly — the
server itself never errors.

## Testing

```bash
pytest                # unit tests for detection + presets
```

Live provider smoke tests are not auto-run; supply credentials and call
`humanize_text` from any MCP client to verify a full round-trip.

## Source provenance

| File | Original source |
|---|---|
| `src/humanize_mcp/detection.py` | `humanize/backend/readability.py` (verbatim) |
| `src/humanize_mcp/prompts.py` | `socmedia/services/llm.py::humanize_text` |
| `src/humanize_mcp/deep_scan.py` | `humanize-checker/app.py` (Streamlit stripped) |
| `src/humanize_mcp/providers/bedrock_provider.py` | `socmedia/services/llm.py::_converse` |
| `src/humanize_mcp/providers/openai_provider.py` | `humanize/backend/llm.py` |
| `src/humanize_mcp/providers/anthropic_provider.py` | new |
