import asyncio
import base64
import json
import os
from typing import List, Optional

import fitz  # PyMuPDF
from mcp.server.fastmcp import Context, FastMCP

# Optional providers
ANTHROPIC_AVAILABLE = False
OPENAI_AVAILABLE = False

try:
    import anthropic  # type: ignore
    ANTHROPIC_AVAILABLE = True
except Exception:
    pass

try:
    from openai import OpenAI  # type: ignore
    OPENAI_AVAILABLE = True
except Exception:
    pass


SERVER_NAME = "ACORD25 PDF -> JSON (Vision)"

PROMPT = (
    "CRITICAL VALIDATION: \n\n"
    "Your FIRST task is to determine if the provided document is a genuine ACORD 25 Certificate of Liability Insurance (COI) form. \n\n"
    "- You MUST be at least 95% certain it is an ACORD 25 COI. \n\n"
    "- If you are less than 95% certain, or if the document is not an ACORD 25 COI, you MUST immediately return only the literal JSON value: null \n\n"
    "- Do NOT attempt to extract or hallucinate any data if you are not sure. \n\n"
    "- Do NOT return any other text, explanation, or JSON structure. Just return null. \n\n"
    "How to identify an ACORD 25 COI: \n\n"
    "- Look for key terms such as \"Certificate of Liability Insurance\", \"ACORD 25\", \"INSURER(S) AFFORDING COVERAGE\", \"CERTIFICATE HOLDER\", \"PRODUCER\", \"POLICY NUMBER\", \"EFFECTIVE DATE\", \"LIABILITY\", etc. \n\n"
    "- If these terms are missing or the document appears to be a different type of form, return null. \n\n"
    "If the document is a valid ACORD 25 COI, proceed with extraction as instructed below. \n\n"
    "### \ud83d\udccd INSURER INFORMATION EXTRACTION \n\n"
    "**FIRST**: Extract all insurer information from the **\"INSURER(S) AFFORDING COVERAGE\"** section at the top right of the form: \n\n"
    "- For each insurer (A, B, C, D, E, F, etc.), extract: \n\n"
    "- `insurer_letter`: The letter (A, B, C, etc.) \n\n"
    "- `insurer_name`: Full insurer name \n\n"
    "- `naic_code`: NAIC number \n\n"
    "### \ud83d\udccb POLICY EXTRACTION RULES \n\n"
    "For each policy in the COVERAGES section: \n\n"
    "- **CRITICAL**: Carefully read the `INSR LTR` column for each policy row. This is the first column in the coverage table. \n\n"
    "- Extract the exact letter (A, B, C, D, E, F, etc.) from the `INSR LTR` column - **DO NOT MAP TO INSURER NAME** \n\n"
    "- **DOUBLE-CHECK**: Make sure you're reading the correct letter for each policy row. Each policy should have its own unique INSR LTR value. \n\n"
    "- **IMPORTANT**: Do NOT assume alphabetical order or patterns. Read the actual letter from the INSR LTR column for each policy. \n\n"
    "- Just return the letter as-is in the `insurer_letter` field \n\n"
    "- Extract all other policy information (type, number, dates, coverages) \n\n"
    "- Normalize dollar values (e.g., `$1,000,000` → `1000000`) \n\n"
    "- Use `limit_type` for the coverage label (e.g., `\"EACH OCCURRENCE\"`, `\"MED EXP\"`) \n\n"
    "- **CRITICAL RULE**: If a coverage limit value is 0, null, empty, or shows only \"$\" with no amount, DO NOT include that coverage in the results. Skip it entirely. \n\n"
    "- **NULL VALUES**: If any field has no information, use `null` instead of empty strings `\"\"` \n\n"
    "### \ud83c\udfaf CERTIFICATE HOLDER EXTRACTION \n\n"
    "- **certificate_holder**: Extract **ONLY the first line** under the \"CERTIFICATE HOLDER\" section. This should be just the business name (e.g., \"JanCo FS 3, LLC Dba Velociti Services\"). Do NOT include any address lines. \n\n"
    "### \ud83c\udfaf SPECIFIC INSTRUCTIONS FOR PRODUCER INFORMATION \n\n"
    "- **full_name**: Extract the **contact person's name** from the **\"NAME\" field** under the PRODUCER section. This should be a real person's name (like \"John Smith\", \"Jane Doe\"). If the NAME field is blank or contains a business name, return null. \n\n"
    "- **doing_business_as**: Extract the **agency/brokerage name** from the **first line directly underneath the \"PRODUCER\" title** on the form. This is the business name of the insurance agency (like \"TechInsurance\", \"ABC Insurance Agency\"). If no value is present, return null. \n\n"
    "- **email_address**: Extract from the \"E-MAIL ADDRESS\" field. If blank, return null. \n\n"
    "### \ud83d\udcde PHONE NUMBER NORMALIZATION (CRITICAL) \n\n"
    "- **fax_number**: Extract from the \"FAX\" field and normalize (remove formatting). If blank, return null. \n\n"
    "- **license_number**: Extract from the **\"License#\" field in the INSURED section** (not the PRODUCER section). This field is typically located near the top of the form, often in the upper left area. Extract the numeric value (e.g., \"3000645669\"). **IMPORTANT**: If the field is blank, return null. \n\n"
    "### \ud83d\uddcf\ufe0f RETURN THIS JSON STRUCTURE \n\n"
    "Return ONLY the JSON data in this exact format, enclosed in {}: \n\n"
    "{ \n\n"
    "\"certificate_information\": { \n\n"
    "\"certificate_holder\": \"string\", \n\n"
    "\"certificate_number\": \"string\", \n\n"
    "\"revision_number\": \"string or null\", \n\n"
    "\"issue_date\": \"MM/DD/YYYY\" \n\n"
    "}, \n\n"
    "\"insurers\": [ \n\n"
    "{ \n\n"
    "\"insurer_letter\": \"string (A, B, C, etc.)\", \n\n"
    "\"insurer_name\": \"string\", \n\n"
    "\"naic_code\": \"string\" \n\n"
    "} \n\n"
    "], \n\n"
    "\"policies\": [ \n\n"
    "{ \n\n"
    "\"policy_information\": { \n\n"
    "\"policy_type\": \"string\", \n\n"
    "\"policy_number\": \"string\", \n\n"
    "\"effective_date\": \"MM/DD/YYYY\", \n\n"
    "\"expiry_date\": \"MM/DD/YYYY\" \n\n"
    "}, \n\n"
    "\"insurer_letter\": \"string (A, B, C, etc.)\", \n\n"
    "\"coverages\": [ \n\n"
    "{ \n\n"
    "\"limit_type\": \"string\", \n\n"
    "\"limit_value\": number \n\n"
    "} \n\n"
    "] \n\n"
    "} \n\n"
    "], \n\n"
    "\"producer_information\": { \n\n"
    "\"primary_details\": { \n\n"
    "\"full_name\": \"string or null\", \n\n"
    "\"email_address\": \"string or null\", \n\n"
    "\"doing_business_as\": \"string or null\" \n\n"
    "}, \n\n"
    "\"contact_information\": { \n\n"
    "\"phone_number\": \"string (digits only, no formatting)\", \n\n"
    "\"fax_number\": \"string (digits only, no formatting) or null\", \n\n"
    "\"license_number\": \"string or null\" \n\n"
    "}, \n\n"
    "\"address_details\": { \n\n"
    "\"address_line_1\": \"string\", \n\n"
    "\"address_line_2\": \"string or null\", \n\n"
    "\"address_line_3\": \"string or null\", \n\n"
    "\"city\": \"string\", \n\n"
    "\"state\": \"string\", \n\n"
    "\"zip_code\": \"string\", \n\n"
    "\"country\": \"USA\" \n\n"
    "} \n\n"
    "} \n\n"
    "} \n\n"
    "--- \n\n"
    "IMPORTANT: If the provided document is NOT an ACORD 25 Certificate of Liability Insurance (COI) form, or if you are not at least 95% certain it is, return only null. Do NOT attempt to extract or hallucinate any data. If in doubt, return null. Do NOT return any other text, explanation, or JSON structure. Just return null."
)


server = FastMCP(SERVER_NAME)


def render_pdf_first_pages_to_png_b64(pdf_path: str, max_pages: int = 5, dpi: int = 180) -> List[str]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if max_pages <= 0:
        raise ValueError("max_pages must be >= 1")

    doc = fitz.open(pdf_path)
    images_b64: List[str] = []
    try:
        num_pages = min(len(doc), max_pages)
        for page_index in range(num_pages):
            page = doc.load_page(page_index)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            images_b64.append(base64.b64encode(png_bytes).decode("ascii"))
    finally:
        doc.close()
    if not images_b64:
        raise ValueError("No pages rendered from PDF")
    return images_b64


def choose_provider_env(provider: Optional[str]) -> str:
    p = (provider or "").strip().lower()
    if p in {"anthropic", "openai"}:
        return p
    # Auto-detect by env
    if os.getenv("ANTHROPIC_API_KEY") and ANTHROPIC_AVAILABLE:
        return "anthropic"
    if os.getenv("OPENAI_API_KEY") and OPENAI_AVAILABLE:
        return "openai"
    # Fallback preference
    if ANTHROPIC_AVAILABLE:
        return "anthropic"
    if OPENAI_AVAILABLE:
        return "openai"
    raise RuntimeError(
        "No supported provider available. Install and set ANTHROPIC_API_KEY or OPENAI_API_KEY."
    )


async def call_anthropic(images_b64: List[str], model: Optional[str]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=api_key)

    content_parts: List[dict] = [{"type": "text", "text": PROMPT}]
    for img_b64 in images_b64:
        content_parts.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            }
        )

    chosen_model = model or os.getenv("ACORD25_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    resp = await asyncio.to_thread(
        lambda: client.messages.create(
            model=chosen_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": content_parts}],
        )
    )

    # Extract concatenated text from message content
    text_chunks: List[str] = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text_chunks.append(getattr(block, "text", ""))
        elif isinstance(block, dict) and block.get("type") == "text":
            text_chunks.append(block.get("text") or "")
    output_text = "\n".join(t for t in text_chunks if t)
    return output_text.strip()


async def call_openai(images_b64: List[str], model: Optional[str]) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=api_key)

    content_items: List[dict] = [{"type": "text", "text": PROMPT}]
    for img_b64 in images_b64:
        content_items.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
            }
        )

    chosen_model = model or os.getenv("ACORD25_OPENAI_MODEL", "gpt-4o")

    resp = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model=chosen_model,
            messages=[{"role": "user", "content": content_items}],
            temperature=0,
        )
    )

    output_text = (
        (resp.choices[0].message.content if resp and resp.choices else None) or ""
    )
    return output_text.strip()


def extract_json_or_null(raw_text: str) -> str:
    t = raw_text.strip()
    # Allow literal null (case-insensitive trim)
    if t.lower() == "null":
        return "null"

    # Try to extract a JSON object from the text
    # Find first '{' and last '}' and attempt to parse
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = t[start : end + 1]
        try:
            obj = json.loads(candidate)
            # Return compacts json (ensure_ascii to preserve chars)
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass

    # If model didn't follow instructions, be safe and return literal null
    return "null"


@server.tool()
async def extract_acord25_from_pdf(
    ctx: Context,
    pdf_path: str,
    max_pages: int = 5,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Process a PDF (first N pages) through a vision LLM and return ONLY JSON or null.

    Args:
        pdf_path: Absolute path to the PDF file accessible by the server.
        max_pages: Max pages from the start of the PDF to include (default 5).
        provider: 'anthropic' or 'openai'. If omitted, auto-detect from env.
        model: Optional model override for the chosen provider.

    Returns:
        A string containing either a JSON object or the literal `null`.
    """
    images_b64 = render_pdf_first_pages_to_png_b64(pdf_path, max_pages=max_pages)
    chosen = choose_provider_env(provider)

    if chosen == "anthropic":
        raw = await call_anthropic(images_b64, model=model)
    elif chosen == "openai":
        raw = await call_openai(images_b64, model=model)
    else:
        raise RuntimeError(f"Unsupported provider: {chosen}")

    return extract_json_or_null(raw)


if __name__ == "__main__":
    server.run()  # run over stdio