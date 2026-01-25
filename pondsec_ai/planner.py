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
        wants_resolution = bool(re.search(r"(wie\s+löse|wie\s+loese|lösen|loesen|resolve|fix|beheben)", message))

        if ticket_ctx.get("type") == "ticket" and ticket_id:
            title = ticket_data.get("title") or "Ticket"
            priority = ticket_data.get("priority") or "unbekannt"
            status = ticket_data.get("status") or "unbekannt"
            description = (ticket_data.get("description") or "").strip()
            description = description[:240] + ("…" if len(description) > 240 else "")
            next_steps = (
                "1) Problem und Scope bestätigen\n"
                "2) Priorität/SLA prüfen und zuständige Person festlegen\n"
                "3) Reproduktion/Logs sammeln\n"
                "4) Lösungsschritte durchführen und dokumentieren\n"
                "5) Rückmeldung geben und Ticket abschließen"
            )

            if wants_summary or wants_resolution:
                plan["summary"] = (
                    f"Zusammenfassung: {title} (Status: {status}, Priorität: {priority}). "
                    f"{description or 'Keine Beschreibung vorhanden.'}\n\n"
                    f"Vermutete nächste Schritte:\n{next_steps}"
                )

            if wants_summary or wants_resolution or wants_internal_note or wants_next_steps:
                plan["steps"].append({
                    "title": "Ticket laden",
                    "tool": "ticket.get",
                    "input": {
                        "ticket_id": ticket_id,
                    },
                })

            if wants_internal_note or wants_next_steps or wants_resolution:
                plan["summary"] = plan["summary"] or "Nächste Schritte für das Ticket."
                plan["steps"].append({
                    "title": "Interne Notiz hinzufügen",
                    "tool": "ticket.add_comment",
                    "input": {
                        "ticket_id": ticket_id,
                        "body": f"Nächste Schritte:\n{next_steps}",
                        "internal": True,
                    },
                })
        elif ticket_ctx.get("type") in {"tickets", "ticket_list"}:
            cleaned = re.sub(r"(ticket|#|\d+)", " ", message, flags=re.IGNORECASE).strip()
            plan["summary"] = (
                "Ich sehe eine Ticket-Liste. Bitte nenne eine Ticket-ID oder wähle ein Ticket aus. "
                "Ich kann sonst nach passenden Tickets suchen."
            )
            plan["steps"].append({
                "title": "Ticket-Suche vorschlagen",
                "tool": "ticket.search",
                "input": {
                    "query": cleaned or message.strip(),
                    "limit": 5,
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
