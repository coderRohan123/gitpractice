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
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    }
  }
}
```

## Tool

- `extract_acord25_from_pdf(pdf_path: str, max_pages: int = 5, provider?: "google"|"gemini"|"anthropic"|"openai", model?: str) -> string`
  - Returns a string that is either a JSON object or the literal `null`.

## Concurrency

- The tool is fully async and offloads blocking tasks (PDF rendering and model calls) to threads, allowing high concurrency.
- With reasonable CPU and IO, handling ~100 concurrent requests is supported. Scale CPU/memory and tune worker limits as needed.

## Notes

- PDF pages are rendered to PNG at 180 DPI for reliable OCR/vision quality.
- The server enforces output to be strict JSON or `null`.
- Provider auto-detection prefers Gemini if `GOOGLE_API_KEY` is set.