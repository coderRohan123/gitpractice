# ACORD 25 MCP Server (PDF -> Vision LLM -> JSON)

This MCP server exposes a tool that takes a PDF, limits it to the first 5 pages (configurable), sends page images to a vision LLM (Anthropic Claude or OpenAI GPT-4o family) with a strict extraction prompt, and returns ONLY a JSON object or `null`.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configure

Set one of the following environment variables:

- `ANTHROPIC_API_KEY` (preferred)
- `OPENAI_API_KEY`

Optional model overrides:

- `ACORD25_ANTHROPIC_MODEL` (default: `claude-3-5-sonnet-latest`)
- `ACORD25_OPENAI_MODEL` (default: `gpt-4o`)

## Run (as MCP server over stdio)

```bash
python mcp_acord25_server.py
```

This will run the server over stdio. Use any MCP client (e.g., Cursor/Claude Desktop) to connect.

Example client config (Cursor `mcp.json` style):

```json
{
  "mcpServers": {
    "acord25": {
      "command": "python",
      "args": ["/workspace/mcp_acord25_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

## Tool

- `extract_acord25_from_pdf(pdf_path: str, max_pages: int = 5, provider?: "anthropic"|"openai", model?: str) -> string`
  - Returns a string that is either a JSON object or the literal `null`.

## Notes

- PDF pages are rendered to PNG with PyMuPDF at 180 DPI for reliable OCR/vision quality.
- The server post-processes the LLM output to ensure only strict JSON or `null` is returned.
- If neither provider is configured/installed, the tool will error with a clear message.