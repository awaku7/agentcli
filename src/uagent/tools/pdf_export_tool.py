# src/uagent/tools/pdf_export_tool.py
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from .i18n_helper import make_tool_translator

_ = make_tool_translator(__file__)

BUSY_LABEL = True
STATUS_LABEL = "tool:pdf_export"

TOOL_SPEC: dict[str, Any] = {
    "load_order": 10,
    "type": "function",
    "tool_genre": "utility",
    "x_parallel_safe": False,
    "function": {
        "name": "pdf_export",
        "description": _(
            "tool.description",
            default="Convert a conversation log file (JSONL) to PDF using Playwright.",
        ),
        "x_search_terms_en": [
            "pdf",
            "export pdf",
            "log to pdf",
            "save as pdf",
            "pdf export",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "log_path": {
                    "type": "string",
                    "description": _(
                        "param.log_path.description",
                        default="Path to the JSONL log file to convert.",
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": _(
                        "param.output_path.description",
                        default="Output path for the PDF file. Defaults to log_path with .pdf extension.",
                    ),
                },
            },
            "required": ["log_path"],
        },
    },
}


def _format_role(role: str) -> str:
    return {
        "user": "You",
        "assistant": "Assistant",
        "system": "System",
        "tool": "Tool",
    }.get(role, role.capitalize())


def _messages_to_html(messages: list[dict[str, Any]]) -> str:
    """Convert a list of message dicts to an HTML conversation view."""
    rows = []
    msg_count = len(messages)
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        label = _format_role(role)
        css_class = f"msg-{role}"

        # Format content
        if isinstance(content, str) and content.strip():
            escaped = (
                content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            formatted = f"<pre>{escaped}</pre>"
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        txt = block.get("text", "")
                        escaped = (
                            txt.replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                        )
                        parts.append(f"<pre>{escaped}</pre>")
                    elif block.get("type") == "tool_use":
                        parts.append(
                            f'<div class="tool-call">[Tool: {block.get("name", "?")}]</div>'
                        )
            formatted = "".join(parts)
        else:
            formatted = ""

        # Tool calls on assistant messages
        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            tc_html = ""
            for tc in tool_calls:
                fname = tc.get("function", {}).get("name", "?")
                tc_html += f'<div class="tool-call">Calling: {fname}</div>'
            formatted = tc_html + formatted

        # Insert page break before every 30th message for long logs
        page_break = ""
        if i > 0 and i % 30 == 0 and msg_count > 30:
            page_break = '<div class="page-break"></div>'

        rows.append(
            f"{page_break}"
            f'<div class="message {css_class}">'
            f'<div class="msg-label">#{i + 1} {label}</div>'
            f'<div class="msg-body">{formatted}</div>'
            f"</div>"
        )

    import datetime

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 20mm 15mm;
  }}
  body {{
    font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #1a1a1a;
    margin: 0;
    padding: 0;
  }}
  h1 {{
    font-size: 16pt;
    border-bottom: 2px solid #333;
    padding-bottom: 6px;
    margin: 0 0 20px 0;
    color: #222;
  }}
  .meta {{
    font-size: 9pt;
    color: #888;
    margin-bottom: 20px;
  }}
  .message {{
    margin-bottom: 10px;
    padding: 8px 12px;
    border-radius: 4px;
    border-left: 4px solid #ddd;
  }}
  .msg-label {{
    font-weight: 600;
    font-size: 9pt;
    margin-bottom: 3px;
    color: #555;
  }}
  .msg-user .msg-label {{ color: #1565c0; }}
  .msg-assistant .msg-label {{ color: #e65100; }}
  .msg-system .msg-label {{ color: #666; }}
  .msg-tool .msg-label {{ color: #6a1b9a; }}
  .msg-body pre {{
    margin: 4px 0;
    white-space: pre-wrap;
    word-break: break-all;
    font-family: "SF Mono", "Courier New", monospace;
    font-size: 8.5pt;
    line-height: 1.4;
  }}
  .msg-user {{ border-left-color: #1565c0; background: #f5f9ff; }}
  .msg-assistant {{ border-left-color: #e65100; background: #fffaf0; }}
  .msg-system {{ border-left-color: #999; background: #f8f8f8; font-size: 9pt; }}
  .msg-tool {{ border-left-color: #6a1b9a; background: #faf5ff; }}
  .tool-call {{
    background: #f0f0f0;
    padding: 2px 8px;
    margin: 4px 0;
    border-radius: 3px;
    font-size: 8pt;
    color: #666;
    font-family: monospace;
  }}
  .page-break {{
    page-break-before: always;
  }}
  @media print {{
    .page-break {{ page-break-before: always; }}
  }}
  .footer {{
    margin-top: 30px;
    padding-top: 10px;
    border-top: 1px solid #ddd;
    font-size: 8pt;
    color: #aaa;
    text-align: center;
  }}
</style>
</head>
<body>
<h1>Conversation Log</h1>
<div class="meta">{msg_count} messages / Generated {now_str}</div>
{''.join(rows)}
<div class="footer">Generated by pdf_export tool</div>
</body>
</html>"""


def _generate_pdf_from_html(html: str, output_path: str) -> None:
    """Use Playwright to generate PDF from HTML."""

    async def _run():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="networkidle")
                await page.pdf(path=output_path, format="A4", print_background=True)
            finally:
                await browser.close()

    asyncio.run(_run())


def run_tool(args: dict[str, Any]) -> str:
    log_path = args.get("log_path", "")
    if not log_path:
        return "Error: log_path is required."

    if not os.path.exists(log_path):
        return f"Error: Log file '{log_path}' does not exist."

    try:
        # Read all messages from the JSONL file
        messages = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        pass  # skip malformed lines
    except Exception as e:
        return f"Error reading log file: {e}"

    if not messages:
        return f"No messages found in '{log_path}'."

    # Limit to avoid huge PDFs
    if len(messages) > 500:
        messages = messages[-500:]
        truncated_note = True
    else:
        truncated_note = False

    html = _messages_to_html(messages)

    if truncated_note:
        html = html.replace(
            "</body>",
            '<div style="color:red;font-weight:bold;">Note: Only the last 500 messages are included.</div></body>',
        )

    output_path = args.get("output_path", "")
    if not output_path:
        base, _ = os.path.splitext(log_path)
        output_path = base + ".pdf"

    try:
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        _generate_pdf_from_html(html, output_path)

        return (
            f"Successfully created PDF at '{output_path}' ({len(messages)} messages)."
        )
    except Exception as e:
        return f"Error generating PDF: {e}"
