"""Agent runtime for PondSec AI."""
from datetime import datetime
import json

from . import context
from .audit import log_action_step, log_tool_decision
from .policy import PolicyEngine, request_approval
from .planner import DeterministicFallbackPlanner, LLMPlanner
from .registry import TOOL_REGISTRY, call_tool


class AgentRuntime:
    def __init__(self, db):
        self.db = db
        self.policy = PolicyEngine(db)
        if self.policy.settings.get("enabled") and LLMPlanner().api_key:
            self.planner = LLMPlanner()
        else:
            self.planner = DeterministicFallbackPlanner()

    def _create_action(self, user_id, context_json, plan_json, summary, risk_level, status):
        now = datetime.utcnow().isoformat()
        cursor = self.db.execute(
            '''
            INSERT INTO agent_actions
                (created_at, created_by_user_id, context_json, plan_json, status, risk_level, summary_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                now,
                user_id,
                json.dumps(context_json or {}),
                json.dumps(plan_json or {}),
                status,
                risk_level,
                summary,
            ),
        )
        self.db.commit()
        return cursor.lastrowid

    def _update_action_status(self, action_id, status):
        self.db.execute(
            'UPDATE agent_actions SET status = ? WHERE id = ?',
            (status, action_id),
        )
        self.db.commit()

    def handle_user_prompt(self, user_ctx, ui_context, message):
        access = user_ctx.get("access") or {}
        ui_ctx = (ui_context or {}).get("ui_context") or {}
        entity_ctx = (ui_context or {}).get("context") or {}
        parsed_refs = context.parse_entity_refs(message)
        explicit_ticket_id = parsed_refs.get("ticket_id")
        effective_context = dict(entity_ctx) if entity_ctx else {}
        list_types = {"tickets", "ticket_list", "unknown"}
        if explicit_ticket_id and (not effective_context or effective_context.get("type") in list_types):
            effective_context = {"type": "ticket", "id": explicit_ticket_id}
        context_payload = {
            "ui_context": ui_ctx,
            "context": effective_context,
            "entity_refs": ui_ctx.get("entity_refs", []) if ui_ctx else [],
            "ticket_id": effective_context.get("id") if effective_context.get("type") == "ticket" else None,
        }
        if explicit_ticket_id and not any(
            ref.get("type") == "ticket" and ref.get("id") == explicit_ticket_id
            for ref in context_payload["entity_refs"]
        ):
            context_payload["entity_refs"].append({"type": "ticket", "id": explicit_ticket_id})
        if context_payload.get("ticket_id"):
            ticket = self.db.execute(
                "SELECT id, title, description, status, priority, requester_name, assignee, due_date FROM tickets WHERE id = ?",
                (context_payload["ticket_id"],),
            ).fetchone()
            if not ticket and explicit_ticket_id:
                return {
                    "insights": (
                        f"Ich konnte kein Ticket mit der ID #{explicit_ticket_id} finden. "
                        "Bitte prüfe die ID oder starte eine Suche."
                    ),
                    "proposed_actions": [
                        {
                            "title": "Ticket-Suche",
                            "rationale": "Ticket-ID nicht gefunden.",
                            "risk": "low",
                            "steps": [{
                                "tool": "ticket.search",
                                "input": {
                                    "query": message.strip() or f"ticket {explicit_ticket_id}",
                                    "limit": 5,
                                },
                            }],
                            "requires_approval": False,
                            "status": "proposed",
                        }
                    ],
                    "references": context_payload.get("entity_refs", []),
                }
            if ticket:
                ticket_dict = dict(ticket)
                if not context.ensure_ticket_access(ticket_dict, access):
                    return {
                        "insights": "Ich habe keine Berechtigung, dieses Ticket zu sehen.",
                        "proposed_actions": [],
                        "references": context_payload.get("entity_refs", []),
                    }
                context_payload["ticket"] = ticket_dict
        plan = self.planner.plan(message, context_payload)
        plan_steps = plan.get("steps", [])
        summary = plan.get("summary", "")
        proposed_actions = []
        if not plan_steps and not summary:
            if entity_ctx.get("type") and not entity_ctx.get("id"):
                summary = (
                    "Ich sehe den Kontext, aber es fehlt eine konkrete ID. "
                    "Bitte öffne einen spezifischen Datensatz (z. B. Ticket oder Asset), "
                    "damit ich arbeiten kann."
                )
            else:
                summary = (
                    "Ich sehe aktuell keinen konkreten Datensatz (z. B. Ticket oder Asset), mit dem ich arbeiten kann. "
                    "Öffne bitte ein Ticket oder Asset und versuche es erneut."
                )
        if not plan_steps:
            return {
                "insights": summary,
                "proposed_actions": [],
                "references": context_payload.get("entity_refs", []),
            }
        risk_level = "low"
        for step in plan_steps:
            tool = TOOL_REGISTRY.get(step.get("tool"))
            if tool and tool.risk in {"med", "high"}:
                risk_level = tool.risk
                break
        action_id = self._create_action(
            access.get("user", {}).get("id"),
            context_payload,
            plan,
            summary,
            risk_level,
            "proposed",
        )
        executed_all = True
        for index, step in enumerate(plan_steps):
            tool_name = step.get("tool")
            tool_def = TOOL_REGISTRY.get(tool_name)
            if not tool_def:
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="failed",
                    error="tool_not_found",
                )
                executed_all = False
                continue
            decision = self.policy.evaluate(user_ctx, tool_def)
            log_tool_decision(
                self.db,
                user_id=access.get("user", {}).get("id"),
                action_id=action_id,
                tool_name=tool_name,
                decision=decision["decision"],
                reason=decision["reason"],
                payload={"input": step.get("input"), "ui_context": ui_context},
            )
            if decision["decision"] != "allowed":
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="denied",
                    error=decision["reason"],
                )
                proposed_actions.append({
                    "title": step.get("title") or tool_name,
                    "rationale": decision["reason"],
                    "risk": tool_def.risk,
                    "steps": [step],
                    "requires_approval": decision.get("requires_approval", False),
                    "action_id": action_id,
                    "status": "denied",
                })
                executed_all = False
                continue
            if decision.get("propose_only"):
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="proposed",
                )
                proposed_actions.append({
                    "title": step.get("title") or tool_name,
                    "rationale": decision["reason"],
                    "risk": tool_def.risk,
                    "steps": [step],
                    "requires_approval": decision.get("requires_approval", False),
                    "action_id": action_id,
                    "status": "proposed",
                })
                executed_all = False
                continue
            if decision.get("requires_approval"):
                request_approval(self.db, action_id, access.get("user", {}).get("id"))
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="proposed",
                )
                proposed_actions.append({
                    "title": step.get("title") or tool_name,
                    "rationale": "Approval required",
                    "risk": tool_def.risk,
                    "steps": [step],
                    "requires_approval": True,
                    "action_id": action_id,
                    "status": "pending_approval",
                })
                executed_all = False
                continue
            output, meta = call_tool(user_ctx, tool_name, step.get("input"))
            status = "executed" if meta.get("decision") == "allowed" else "failed"
            log_action_step(
                self.db,
                action_id=action_id,
                step_index=index,
                tool_name=tool_name,
                tool_input=step.get("input"),
                status=status,
                output=output,
                error=None if status == "executed" else meta.get("reason"),
            )
            proposed_actions.append({
                "title": step.get("title") or tool_name,
                "rationale": meta.get("reason"),
                "risk": tool_def.risk,
                "steps": [step],
                "requires_approval": False,
                "action_id": action_id,
                "status": status,
                "output": output,
            })
            if status != "executed":
                executed_all = False
        self._update_action_status(action_id, "executed" if executed_all else "proposed")
        return {
            "insights": summary,
            "proposed_actions": proposed_actions,
            "references": context_payload.get("entity_refs", []),
        }

    def handle_event(self, event_row):
        payload = json.loads(event_row["payload_json"] or "{}")
        title = payload.get("title") or "Ereignis"
        severity = "info"
        if payload.get("priority") in {"high", "urgent"}:
            severity = "critical"
        if "urgent" in (payload.get("title") or "").lower():
            severity = "critical"
        body = f"Event {event_row['type']} für {event_row['entity_type']} #{event_row['entity_id']}"
        self.db.execute(
            '''
            INSERT INTO agent_alerts (created_at, severity, title, body, entity_refs_json, status)
            VALUES (?, ?, ?, ?, ?, 'open')
            ''',
            (
                datetime.utcnow().isoformat(),
                severity,
                f"PondSec AI: {title}",
                body,
                json.dumps([{"type": event_row["entity_type"], "id": event_row["entity_id"]}]),
            ),
        )
        self.db.commit()

    def execute_action(self, action_id, user_ctx):
        action = self.db.execute(
            'SELECT * FROM agent_actions WHERE id = ?',
            (action_id,),
        ).fetchone()
        if not action:
            return {"status": "not_found"}
        plan = json.loads(action["plan_json"] or "{}")
        steps = plan.get("steps", [])
        executed_all = True
        for index, step in enumerate(steps):
            tool_name = step.get("tool")
            tool_def = TOOL_REGISTRY.get(tool_name)
            if not tool_def:
                executed_all = False
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="failed",
                    error="tool_not_found",
                )
                continue
            decision = self.policy.evaluate(user_ctx, tool_def)
            if decision["decision"] != "allowed":
                executed_all = False
                log_tool_decision(
                    self.db,
                    user_id=user_ctx.get("access", {}).get("user", {}).get("id"),
                    action_id=action_id,
                    tool_name=tool_name,
                    decision=decision["decision"],
                    reason=decision["reason"],
                    payload={"input": step.get("input")},
                )
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="denied",
                    error=decision["reason"],
                )
                continue
            output, meta = call_tool(user_ctx, tool_name, step.get("input"))
            status = "executed" if meta.get("decision") == "allowed" else "failed"
            log_action_step(
                self.db,
                action_id=action_id,
                step_index=index,
                tool_name=tool_name,
                tool_input=step.get("input"),
                status=status,
                output=output,
                error=None if status == "executed" else meta.get("reason"),
            )
            if status != "executed":
                executed_all = False
        self._update_action_status(action_id, "executed" if executed_all else "failed")
        return {"status": "executed" if executed_all else "failed"}
