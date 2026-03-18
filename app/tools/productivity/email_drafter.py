"""
Email Drafter Tool — Draft professional emails from instructions or bullet points.
LLM-powered with tone, context, and recipient support.
"""

import json
import logging

from langchain_core.tools import tool
from app.tools.base import nurav_tool, ToolMetadata, ToolStatus, ToolExample

logger = logging.getLogger(__name__)

TONE_GUIDES = {
    "formal": "Use formal English. Start with 'Dear [Name]'. Professional and respectful. End with 'Yours sincerely' or 'Best regards'.",
    "friendly": "Warm and approachable tone. Conversational but still professional. End with 'Best' or 'Thanks'.",
    "concise": "Extremely brief. Get straight to the point. No pleasantries. Bullet points where appropriate.",
    "persuasive": "Compelling and action-oriented. Use clear benefits, social proof, and strong calls to action.",
    "apologetic": "Empathetic and sincere. Acknowledge the issue, take responsibility, explain next steps.",
    "follow_up": "Brief reminder that doesn't come across as pushy. Reference the previous communication.",
}


@nurav_tool(metadata=ToolMetadata(
    name="email_drafter",
    description="Draft professional emails from instructions, bullet points, or context. Supports 6 tones: formal, friendly, concise, persuasive, apologetic, follow_up. Generates subject line and full body.",
    niche="productivity",
    status=ToolStatus.ACTIVE,
    icon="mail",
    version="1.0.0",
    examples=[
        ToolExample(
            input={"instructions": "Follow up on project proposal sent last week. Ask if they have questions.", "tone": "friendly", "recipient": "The client"},
            output='{"subject": "Following Up: Project Proposal", "body": "Hi,\\n\\nI wanted to check in...", "tone": "friendly"}',
            description="Draft a friendly follow-up email",
        ),
    ],
    input_schema={"instructions": "str", "tone": "str ('formal'|'friendly'|'concise'|'persuasive'|'apologetic'|'follow_up')", "context": "str (optional background)", "recipient": "str (optional)"},
    output_schema={"subject": "str", "body": "str", "tone": "str", "word_count": "int"},
    avg_response_ms=3000,
    success_rate=0.96,
))
@tool
async def email_drafter(instructions: str, tone: str = "formal", context: str = "", recipient: str = "") -> str:
    """Draft a professional email."""
    if not instructions.strip():
        return json.dumps({"error": "No instructions provided."})

    tone = tone.lower().strip()
    if tone not in TONE_GUIDES:
        tone = "formal"

    try:
        from app.services.llm_service import get_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        context_note = f"\nBackground context: {context}" if context.strip() else ""
        recipient_note = f"\nRecipient: {recipient}" if recipient.strip() else ""

        system = f"""You are an expert email writing assistant.
Tone guidance: {TONE_GUIDES[tone]}{context_note}{recipient_note}

Write a complete, ready-to-send email based on the instructions.
Respond ONLY with valid JSON:
{{
  "subject": "Email subject line",
  "body": "Complete email body (use \\n for line breaks)",
  "key_points": ["main point 1", "main point 2"],
  "call_to_action": "The specific action you want the recipient to take"
}}"""

        llm = get_llm(provider="google")
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Draft an email for:\n\n{instructions}"),
        ])
        result_text = resp.content.strip()
        if result_text.startswith("```"):
            result_text = "\n".join(result_text.split("\n")[1:-1])

        result = json.loads(result_text)
        body = result.get("body", "")
        return json.dumps({
            "subject": result.get("subject", ""),
            "body": body,
            "tone": tone,
            "key_points": result.get("key_points", []),
            "call_to_action": result.get("call_to_action", ""),
            "word_count": len(body.split()),
        })
    except json.JSONDecodeError:
        # LLM may have returned plain text email
        text = resp.content.strip() if 'resp' in locals() else ""
        lines = text.split("\n")
        subject = lines[0].replace("Subject:", "").strip() if lines else "Email"
        body = "\n".join(lines[1:]).strip()
        return json.dumps({"subject": subject, "body": body, "tone": tone, "word_count": len(body.split())})
    except Exception as e:
        return json.dumps({"error": f"Email drafting failed: {str(e)}"})
