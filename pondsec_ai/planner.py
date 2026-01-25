"""Planner implementations for PondSec AI."""
import json
import os
import re
import urllib.request


class Planner:
    def plan(self, user_message, context):
        raise NotImplementedError


class DeterministicFallbackPlanner(Planner):
    def plan(self, user_message, context):
        message = (user_message or "").lower()
        plan = {
            "summary": "",
            "steps": [],
        }
        if not message.strip():
            return plan
        ticket_ctx = context.get("context") or {}
        ticket_id = context.get("ticket_id")
        ticket_data = context.get("ticket") or {}
        wants_summary = any(keyword in message for keyword in ("fasse", "zusammenfassung", "zusammenfassen"))
        wants_internal_note = any(keyword in message for keyword in ("interne notiz", "interner kommentar", "internal note", "notiz erstellen"))
        wants_next_steps = any(keyword in message for keyword in ("nächste schritte", "next steps"))

        if ticket_ctx.get("type") == "ticket" and ticket_id:
            if wants_summary:
                # Provide a short, safe summary without executing tools.
                title = ticket_data.get("title") or "Ticket"
                priority = ticket_data.get("priority") or "unbekannt"
                status = ticket_data.get("status") or "unbekannt"
                description = (ticket_data.get("description") or "").strip()
                description = description[:240] + ("…" if len(description) > 240 else "")
                plan["summary"] = (
                    f"Zusammenfassung: {title} (Status: {status}, Priorität: {priority}). "
                    f"{description or 'Keine Beschreibung vorhanden.'}"
                )

            if wants_internal_note or wants_next_steps:
                plan["summary"] = plan["summary"] or "Nächste Schritte für das Ticket."
                plan["steps"].append({
                    "title": "Interne Notiz hinzufügen",
                    "tool": "ticket.comment",
                    "input": {
                        "ticket_id": ticket_id,
                        "body": "Nächste Schritte: Ticket priorisieren, Verantwortliche:n festlegen, SLA prüfen und Rückmeldung an den/die Anfragende:n geben.",
                        "internal_note": True,
                    },
                })

        if re.search(r"(urgent|kritisch|sofort|sla)", message):
            plan["summary"] = plan["summary"] or "Dringlichkeits-Alert erstellen"
            plan["steps"].append({
                "title": "Alert erstellen",
                "tool": "alert.create",
                "input": {
                    "severity": "critical",
                    "title": "PondSec AI: Dringliche Anfrage erkannt",
                    "body": "Der Benutzer markierte die Anfrage als dringend/SLA-relevant.",
                    "entity_refs": context.get("entity_refs", []),
                },
            })
        return plan


class LLMPlanner(Planner):
    def __init__(self, model=None):
        self.model = model or os.environ.get("PONDSEC_AI_MODEL", "gpt-4o-mini")
        self.api_key = os.environ.get("OPENAI_API_KEY")

    def plan(self, user_message, context):
        if not self.api_key:
            return DeterministicFallbackPlanner().plan(user_message, context)
        prompt = {
            "message": user_message,
            "context": context,
            "instruction": "Return strict JSON with keys summary and steps."
        }
        data = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a tool planning assistant. Reply ONLY with JSON."},
                {"role": "user", "content": json.dumps(prompt)},
            ],
            "temperature": 0.1,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return DeterministicFallbackPlanner().plan(user_message, context)
        try:
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception:
            return DeterministicFallbackPlanner().plan(user_message, context)
