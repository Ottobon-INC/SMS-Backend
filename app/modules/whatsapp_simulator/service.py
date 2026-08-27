"""WhatsApp Simulator Service with SSE broadcasting and template rendering."""

import asyncio
import json
import logging, time
from datetime import datetime
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)

META_TEMPLATES = {
    "exam_results_published_v1": {
        "name": "exam_results_published_v1",
        "category": "UTILITY",
        "header": "ACADEMIC EXAM RESULT PUBLISHED",
        "body": "Dear Parent of *{{1}}*,\n\nThe exam results for *{{2}}* (Date: {{3}}) have been published.\n\n*MARK DETAILS:*\n{{4}}\n----------------------------------------\n*TOTAL SCORE:* {{5}}\n*PERCENTAGE:* {{6}}%\n*FINAL STATUS:* *{{7}}*\n----------------------------------------\nLog in to the Student Portal to view full report cards.\n- *{{8}}* Academic Cell",
    },
    "single_student_correction_v1": {
        "name": "single_student_correction_v1",
        "category": "UTILITY",
        "header": "UPDATED EXAM RESULT NOTICE",
        "body": "Dear Parent of *{{1}}*,\n\nUpdated exam marks have been posted for *{{2}}* (Date: {{3}}).\n\n*UPDATED MARK DETAILS:*\n{{4}}\n----------------------------------------\n*UPDATED TOTAL:* {{5}}\n*UPDATED PERCENTAGE:* {{6}}%\n*UPDATED STATUS:* *{{7}}*\n----------------------------------------\n- *{{8}}* Principal & Academic Office",
    },
    "fee_payment_receipt_v1": {
        "name": "fee_payment_receipt_v1",
        "category": "UTILITY",
        "header": "FEE PAYMENT RECEIPT CONFIRMATION",
        "body": "Dear Parent of *{{1}}*,\n\nWe have received a fee payment transaction for *{{2}}*.\n\n*Receipt Number:* {{3}}\n*Receipt Date:* {{4}}\n*Amount Paid:* *Rs. {{5}}*\n*Payment Mode:* {{6}}\n*Remaining Balance:* *Rs. {{7}}*\n----------------------------------------\nThank you,\n- *{{8}}* Accounts Office",
    },
    "fee_due_reminder_v1": {
        "name": "fee_due_reminder_v1",
        "category": "UTILITY",
        "header": "UPCOMING FEE DUE REMINDER",
        "body": "Dear *{{1}}*,\n\nA gentle reminder that fee dues for *{{2}}* (Adm No: *{{3}}*, Session: *{{4}}*) of *Rs. {{5}}* are due on *{{6}}*.\n----------------------------------------\nPlease clear the pending fee dues at your earliest convenience. Please ignore if already paid.\n- *{{7}}*",
    },
    "attendance_absent_v1": {
        "name": "attendance_absent_v1",
        "category": "UTILITY",
        "header": "DAILY ATTENDANCE ALERT (ABSENT)",
        "body": "Dear Parent of *{{1}}*,\n\nYour child *{{1}}* (Section: *{{2}}*) was marked *ABSENT* for today's classes on {{3}}.\n----------------------------------------\nPlease contact the campus office if this was an error.\n- *{{4}}* Attendance Cell",
    },
}


def render_meta_template(template_name: str, parameters: list[str]) -> dict[str, str]:
    """Renders a Meta WhatsApp template body with positional placeholders {{1}}, {{2}}, etc."""
    meta_obj = META_TEMPLATES.get(template_name)
    if not meta_obj:
        return {
            "templateName": template_name,
            "header": "NOTIFICATION",
            "category": "UTILITY",
            "body": f"[Meta Template: {template_name}]\nParams: {parameters}",
        }

    filled_body = meta_obj["body"]
    for idx, val in enumerate(parameters):
        placeholder = f"{{{{{idx + 1}}}}}"
        filled_body = filled_body.replace(placeholder, str(val or ""))

    return {
        "templateName": meta_obj["name"],
        "header": meta_obj["header"],
        "category": meta_obj["category"],
        "body": filled_body,
    }


class WhatsAppSimulatorManager:
    """Manages in-memory message logs and SSE subscriber queues."""

    def __init__(self):
        self.recent_messages: list[dict[str, Any]] = []
        self.max_messages: int = 100
        self.subscribers: set[asyncio.Queue] = set()

    def add_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Formated and stores an outbound message payload into recent_messages."""
        to_phone = payload.get("to") or "+919876543210"
        wamid = f"wamid.HBgL{int(time.time() * 1000)}{hash(to_phone) % 1000}"

        msg_type = payload.get("type", "template")
        rendered: dict[str, str] = {}

        if msg_type == "template" and payload.get("template"):
            tpl = payload["template"]
            template_name = tpl.get("name", "")
            components = tpl.get("components") or []
            body_comp = next((c for c in components if c.get("type") == "body"), None)
            raw_params = body_comp.get("parameters", []) if body_comp else []
            param_strings = []
            for p in raw_params:
                if isinstance(p, str):
                    param_strings.append(p)
                elif isinstance(p, dict):
                    param_strings.append(str(p.get("text", "")))
                else:
                    param_strings.append(str(p))

            rendered = render_meta_template(template_name, param_strings)
        elif msg_type == "text" and payload.get("text"):
            rendered = {
                "templateName": "raw_text",
                "header": "NOTIFICATION",
                "category": "UTILITY",
                "body": payload["text"].get("body", ""),
            }
        else:
            rendered = {
                "templateName": "raw_json",
                "header": "NOTIFICATION",
                "category": "UTILITY",
                "body": json.dumps(payload, indent=2),
            }

        msg_obj = {
            "id": wamid,
            "timestamp": datetime.now().isoformat(),
            "toPhone": to_phone,
            "type": msg_type,
            "templateName": rendered.get("templateName", "unknown"),
            "header": rendered.get("header", "NOTIFICATION"),
            "category": rendered.get("category", "UTILITY"),
            "body": rendered.get("body", ""),
        }

        self.recent_messages.append(msg_obj)
        if len(self.recent_messages) > self.max_messages:
            self.recent_messages = self.recent_messages[-self.max_messages :]

        # Broadcast to active SSE listeners
        event_data = json.dumps({"type": "outbound_notification", "message": msg_obj})
        dead_queues = set()
        for q in self.subscribers:
            try:
                q.put_nowait(event_data)
            except Exception:
                dead_queues.add(q)
        for dead in dead_queues:
            self.subscribers.discard(dead)

        return msg_obj

    def get_messages(self) -> list[dict[str, Any]]:
        return self.recent_messages

    def clear_messages(self) -> None:
        self.recent_messages.clear()
        event_data = json.dumps({"type": "messages_cleared"})
        dead_queues = set()
        for q in self.subscribers:
            try:
                q.put_nowait(event_data)
            except Exception:
                dead_queues.add(q)
        for dead in dead_queues:
            self.subscribers.discard(dead)

    async def stream_events(self) -> AsyncGenerator[str, None]:
        q = asyncio.Queue()
        self.subscribers.add(q)

        try:
            # Yield initial connection ready event
            yield f"data: {json.dumps({'type': 'connection_ready'})}\n\n"

            # Yield existing backlog
            for msg in self.recent_messages:
                yield f"data: {json.dumps({'type': 'outbound_notification', 'message': msg})}\n\n"

            while True:
                data = await q.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.subscribers.discard(q)


simulator_manager = WhatsAppSimulatorManager()
