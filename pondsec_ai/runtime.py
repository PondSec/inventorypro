"""Agent runtime for PondSec AI."""
from datetime import datetime
import json

from . import context
from .audit import log_action_step, log_tool_decision
from .policy import PolicyEngine, request_approval
from .planner import LocalLLMPlanner
from .registry import TOOL_REGISTRY, call_tool


class AgentRuntime:
    def __init__(self, db):
        self.db = db
        self.policy = PolicyEngine(db)
        self.planner = LocalLLMPlanner()

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

    def _system_ctx(self):
        roles = self.db.execute('SELECT id FROM roles WHERE is_superuser = 1').fetchall()
        return {
            "access": {"user": {"id": None}, "is_superuser": True, "permissions": []},
            "roles": [dict(row) for row in roles],
        }

    def _should_create_alert(self, tool_input, minutes=30):
        title = tool_input.get("title")
        entity_refs = tool_input.get("entity_refs") or []
        if not title or not entity_refs:
            return True
        cutoff = (datetime.utcnow().timestamp() - minutes * 60)
        since = datetime.utcfromtimestamp(cutoff).isoformat()
        for ref in entity_refs:
            ref_id = ref.get("id")
            ref_type = ref.get("type")
            if not ref_id or not ref_type:
                continue
            row = self.db.execute(
                '''
                SELECT 1 FROM agent_alerts
                WHERE title = ? AND created_at >= ? AND entity_refs_json LIKE ?
                LIMIT 1
                ''',
                (title, since, f'%\"type\": \"{ref_type}\"%\"id\": {ref_id}%'),
            ).fetchone()
            if row:
                return False
        return True

    def handle_user_prompt(self, user_ctx, ui_context, message):
        access = user_ctx.get("access") or {}
        ui_ctx = (ui_context or {}).get("ui_context") or {}
        raw_context = (ui_context or {}).get("context") or {}
        entity_ctx = context.normalize_context(raw_context)
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
        plan_actions = plan.get("actions", [])
        if not isinstance(plan_actions, list):
            plan_actions = []
        summary = plan.get("insights", "")
        questions = plan.get("questions", [])
        if questions:
            summary = f"{summary}\n\nFragen:\n" + "\n".join(f"- {question}" for question in questions)
        proposed_actions = []
        if not summary:
            summary = "Ich benötige mehr Kontext, um sinnvolle nächste Schritte vorzuschlagen."
        if not plan_actions:
            return {
                "insights": summary,
                "proposed_actions": [],
                "references": context_payload.get("entity_refs", []),
            }
        risk_level = "low"
        for action in plan_actions:
            tool = TOOL_REGISTRY.get(action.get("tool"))
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
        for index, action in enumerate(plan_actions):
            tool_name = action.get("tool")
            step = {
                "title": tool_name,
                "tool": tool_name,
                "input": action.get("input") or {},
            }
            action_rationale = action.get("rationale") or ""
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
                    "rationale": action_rationale or decision["reason"],
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
                    "rationale": action_rationale or "Approval required",
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
                "rationale": action_rationale or meta.get("reason"),
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
        event_context = {
            "context": {"type": event_row["entity_type"], "id": int(event_row["entity_id"])},
            "event": {
                "type": event_row["type"],
                "payload": payload,
            },
            "entity_refs": [{"type": event_row["entity_type"], "id": int(event_row["entity_id"])}],
        }
        if event_row["entity_type"] == "ticket":
            ticket = self.db.execute(
                "SELECT id, title, description, status, priority, requester_name, assignee, due_date FROM tickets WHERE id = ?",
                (event_row["entity_id"],),
            ).fetchone()
            if ticket:
                event_context["ticket_id"] = int(event_row["entity_id"])
                event_context["ticket"] = dict(ticket)
        message = f"Event {event_row['type']}"
        plan = self.planner.plan(message, event_context)
        plan_actions = plan.get("actions", [])
        if not isinstance(plan_actions, list):
            plan_actions = []
        urgent_ticket = False
        if event_row["entity_type"] == "ticket":
            title = (payload.get("title") or event_context.get("ticket", {}).get("title") or "").lower()
            priority = (payload.get("priority") or event_context.get("ticket", {}).get("priority") or "").lower()
            if "urgent" in title or priority in {"urgent", "high", "kritisch"}:
                urgent_ticket = True
        if urgent_ticket and not any(action.get("tool") == "alert.create" for action in plan_actions):
            plan_actions.append({
                "tool": "alert.create",
                "input": {
                    "severity": "critical",
                    "title": f"PondSec AI: URGENT Ticket #{event_row['entity_id']}",
                    "body": "Ein Ticket wurde als dringend erkannt und benötigt schnelle Bearbeitung.",
                    "entity_refs": event_context.get("entity_refs", []),
                },
                "risk": "low",
                "rationale": "Ticket enthält dringende Kennzeichnung im Event.",
                "evidence": [f"ticket:{event_row['entity_id']}"],
            })
        summary = plan.get("insights", "") or "Automatisches Ereignis verarbeitet."
        questions = plan.get("questions", [])
        if questions:
            summary = f"{summary}\n\nFragen:\n" + "\n".join(f"- {question}" for question in questions)
        if not plan_actions:
            return
        risk_level = "low"
        for action in plan_actions:
            tool = TOOL_REGISTRY.get(action.get("tool"))
            if tool and tool.risk in {"med", "high"}:
                risk_level = tool.risk
                break
        action_id = self._create_action(
            None,
            event_context,
            plan,
            summary,
            risk_level,
            "proposed",
        )
        executed_all = True
        system_ctx = self._system_ctx()
        for index, action in enumerate(plan_actions):
            tool_name = action.get("tool")
            step = {"title": tool_name, "tool": tool_name, "input": action.get("input") or {}}
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
            decision = self.policy.evaluate(system_ctx, tool_def)
            log_tool_decision(
                self.db,
                user_id=None,
                action_id=action_id,
                tool_name=tool_name,
                decision=decision["decision"],
                reason=decision["reason"],
                payload={"input": step.get("input"), "event": event_row["type"]},
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
                executed_all = False
                continue
            if decision.get("requires_approval") or decision.get("propose_only"):
                if decision.get("requires_approval"):
                    request_approval(self.db, action_id, None)
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="proposed",
                )
                executed_all = False
                continue
            if tool_name == "alert.create" and not self._should_create_alert(step.get("input"), minutes=30):
                log_action_step(
                    self.db,
                    action_id=action_id,
                    step_index=index,
                    tool_name=tool_name,
                    tool_input=step.get("input"),
                    status="skipped",
                    error="dedupe",
                )
                executed_all = False
                continue
            output, meta = call_tool(system_ctx, tool_name, step.get("input"))
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
        self._update_action_status(action_id, "executed" if executed_all else "proposed")

    def execute_action(self, action_id, user_ctx):
        action = self.db.execute(
            'SELECT * FROM agent_actions WHERE id = ?',
            (action_id,),
        ).fetchone()
        if not action:
            return {"status": "not_found"}
        plan = json.loads(action["plan_json"] or "{}")
        steps = plan.get("actions", [])
        if not isinstance(steps, list):
            steps = []
        executed_all = True
        for index, action in enumerate(steps):
            tool_name = action.get("tool")
            step = {
                "title": tool_name,
                "tool": tool_name,
                "input": action.get("input") or {},
            }
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
