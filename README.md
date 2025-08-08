# ACORD 25 MCP Server (PDF -> Vision LLM -> JSON)

This MCP server exposes a tool that takes a PDF, limits it to the first 5 pages (configurable), sends page images to a vision LLM (Google Gemini, Anthropic, or OpenAI) with a strict extraction prompt, and returns ONLY a JSON object or `null`.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

If a venv is unavailable in your environment, install with `--break-system-packages` or use pipx.

## Configure

Set ONE of the following API keys:

- `GOOGLE_API_KEY` (for Gemini; default model: `gemini-2.5-flash-lite`)
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Optional model overrides:

- `ACORD25_GOOGLE_MODEL` (default: `gemini-2.5-flash-lite`)
- `ACORD25_ANTHROPIC_MODEL` (default: `claude-3-5-sonnet-latest`)
- `ACORD25_OPENAI_MODEL` (default: `gpt-4o`)

Optional performance settings:

- `ACORD25_MAX_CONCURRENCY` (default `100`): max concurrent requests guarded by semaphore.

## Run (as MCP server over stdio)

```bash
python mcp_acord25_server.py
```

Client config example (Cursor `mcp.json` style):

```json
{
  "mcpServers": {
    "acord25": {
      "command": "python",
      "args": ["/workspace/mcp_acord25_server.py"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
        "ACORD25_MAX_CONCURRENCY": "100"
      }
    }
  }
}
```

## Tool

- `extract_acord25_from_pdf(pdf_path: str, max_pages: int = 5, provider?: "google"|"gemini"|"anthropic"|"openai", model?: str, dpi: int = 150) -> string`
  - Returns a string that is either a JSON object or the literal `null`.
  - `dpi` controls PNG render resolution. Lower values reduce payload size and latency; 150 is a good balance.

## Concurrency

- Fully async; blocking PDF rendering and model calls are offloaded to threads.
- Per-page rendering is parallelized for speed.
- With sufficient resources, ~100 concurrent requests is supported; tune `ACORD25_MAX_CONCURRENCY` as needed.

## Notes

- PDF pages are rendered to PNG at configurable DPI (default 150).
- The server enforces output to be strict JSON or `null`.
- Provider auto-detection prefers Gemini if `GOOGLE_API_KEY` is set.