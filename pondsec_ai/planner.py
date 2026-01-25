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
            "summary": "No actionable request detected.",
            "steps": [],
        }
        if not message.strip():
            return plan
        if "ticket" in message and "zusammen" in message:
            ticket_id = context.get("ticket_id")
            if ticket_id:
                plan["summary"] = "Ticket zusammenfassen"
                plan["steps"].append({
                    "title": "Ticket abrufen",
                    "tool": "ticket.get",
                    "input": {"ticket_id": ticket_id},
                })
        if "nächste" in message or "next steps" in message:
            ticket_id = context.get("ticket_id")
            if ticket_id:
                plan["summary"] = "Nächste Schritte als internen Kommentar vorschlagen"
                plan["steps"].append({
                    "title": "Interne Notiz hinzufügen",
                    "tool": "ticket.comment",
                    "input": {
                        "ticket_id": ticket_id,
                        "body": "Vorschlag: Bitte priorisieren, zuständigen Owner bestimmen und SLA prüfen.",
                        "internal_note": True,
                    },
                })
        if re.search(r"(urgent|kritisch|sofort|sla)", message):
            plan["summary"] = "Dringlichkeits-Alert erstellen"
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
        if not plan["steps"]:
            plan["summary"] = "Keine passenden Tools gefunden."
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
