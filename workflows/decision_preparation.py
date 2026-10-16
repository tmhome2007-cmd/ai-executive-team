"""Approved decision preparation: claims, bounded proposals, provenance and private recovery.

This service grants no execution or resource authority. Storage operations are injected
explicitly so routes remain thin and tests preserve the original patch seams.
"""

import ast
from dataclasses import dataclass
import hashlib
import json
import logging
import re
from typing import Any, Callable, Mapping


class PreparationError(Exception):
    """A safe owner-facing domain error with an HTTP status for boundary translation."""

    def __init__(self, *, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class PreparationDependencies:
    """Explicit application seams; callbacks retain transactional ownership in storage."""

    get_decision_by_id: Callable[..., Any]
    get_company_goal: Callable[..., Any]
    claim_decision_for_preparation: Callable[..., Any]
    run_executive_meeting: Callable[..., Any]
    agents: Mapping[str, Any]
    get_action_by_id: Callable[..., Any]
    get_resource_request_by_id: Callable[..., Any]
    propose_resource_request: Callable[..., Any]
    action_provenance_scope: Callable[..., Any]
    finish_decision_preparation: Callable[..., Any]
    get_executive_profiles: Callable[..., Any]
    send_notification: Callable[..., Any]
    logger: logging.Logger


class DecisionPreparation:
    """One preparation attempt; instance state cannot be shared between requests."""

    def __init__(
        self,
        decision_id: int,
        agent_keys: list[str],
        dependencies: PreparationDependencies,
    ):
        self.decision_id = decision_id
        self.agent_keys = agent_keys
        self.dependencies = dependencies

    def prepare(self):
        """
        Phase 2: laat tool-capable executives een GOEDGEKEURDE strategische
        beslissing vertalen naar concrete voorbereiding/action proposals en
        structured resource requests. Niets wordt direct uitgevoerd of verleend.
        """
        decision_id = self.decision_id
        decision = self.dependencies.get_decision_by_id(decision_id)
        if decision is None:
            raise PreparationError(status_code=404, detail="Decision not found.")
        if decision["approval_status"] != "approved":
            raise PreparationError(
                status_code=409,
                detail=f"Decision must be approved before preparation (currently '{decision['approval_status']}').",
            )
        if decision.get("goal_id") is not None:
            goal = self.dependencies.get_company_goal(decision["goal_id"])
            if goal is None:
                raise PreparationError(
                    status_code=409,
                    detail="Decision references a goal that no longer exists.",
                )
            if goal["status"] != "active":
                raise PreparationError(
                    status_code=409,
                    detail=f"Linked company goal must remain active before preparation (currently '{goal['status']}').",
                )
        else:
            goal = None
        if not self.dependencies.claim_decision_for_preparation(decision_id):
            current = self.dependencies.get_decision_by_id(decision_id)
            raise PreparationError(
                status_code=409,
                detail=f"Decision preparation could not be claimed (current preparation status: '{(current.get('preparation_status') if current else 'unknown')}').",
            )
        self.decision = decision
        trusted_browser_context = "\n".join(
            (
                part
                for part in (
                    decision.get("task_description"),
                    decision.get("decision_outcome"),
                    goal.get("description") if goal else None,
                    goal.get("success_criteria") if goal else None,
                )
                if part
            )
        )
        allowed_browser_urls = set(
            re.findall("https?://[^\\s<>\"\\')\\]}]+", trusted_browser_context)
        )
        self.allowed_browser_urls = allowed_browser_urls
        preparation_prompt = self._build_prompt(decision, goal)
        try:
            meeting_result, final_plan, participants = self._prepare_proposals(
                preparation_prompt
            )
            self.dependencies.finish_decision_preparation(
                decision_id,
                True,
                final_plan,
                individual_outputs=meeting_result.get("individual_outputs", {}),
                executive_profiles=self.dependencies.get_executive_profiles(),
            )
        except PreparationError:
            raise
        except ValueError as e:
            self.dependencies.finish_decision_preparation(decision_id, False, None)
            self.dependencies.logger.warning(
                "preparation_invalid decision_id=%s error_type=%s",
                decision_id,
                type(e).__name__,
            )
            raise PreparationError(
                status_code=400,
                detail="Invalid preparation request; review the selected agents and supplied inputs.",
            ) from None
        except Exception as e:
            self.dependencies.finish_decision_preparation(decision_id, False, None)
            self.dependencies.logger.warning(
                "preparation_failed decision_id=%s error_type=%s",
                decision_id,
                type(e).__name__,
            )
            raise PreparationError(
                status_code=502,
                detail="Preparation meeting failed; no execution authority was granted. Review local provider availability before retrying.",
            ) from None
        try:
            self.dependencies.send_notification(
                f"🧭 <b>PREPARATION COMPLETE</b>\n\n<b>Source decision:</b> #{decision_id}\n\nAny concrete actions and resource requests proposed by executives are still waiting for separate owner review."
            )
        except Exception as notify_err:
            self.dependencies.logger.warning(
                "preparation_notification_failed decision_id=%s error_type=%s",
                decision_id,
                type(notify_err).__name__,
            )
        return dict(
            source_decision_id=decision_id,
            final_plan=final_plan,
            participants=participants,
            individual_outputs=meeting_result.get("individual_outputs", {}),
            quality_warnings=meeting_result.get("quality_warnings", {}),
        )

    def _prepare_proposals(self, preparation_prompt):
        """Run one attempt and a bounded resource retry; verify every persisted proposal."""
        decision_id = self.decision_id
        meeting_result = self._run_preparation_meeting(preparation_prompt)
        participants = meeting_result.get("participants", [])
        final_plan = meeting_result.get("final_decision", "")
        (
            proposed_action_ids,
            proposed_resource_request_ids,
            new_actions,
            new_resource_requests,
        ) = self._load_created_items(meeting_result)
        provenance_mismatches, resource_provenance_mismatches = (
            self._provenance_mismatches(
                proposed_action_ids,
                proposed_resource_request_ids,
                new_actions,
                new_resource_requests,
            )
        )
        if provenance_mismatches:
            self.dependencies.finish_decision_preparation(
                decision_id,
                False,
                "Preparation failed provenance verification; orphan/mismatched action detected.",
            )
            raise PreparationError(
                status_code=502,
                detail="Preparation created an action without the expected decision provenance. Preparation was marked failed; do not approve the orphan action.",
            )
        if resource_provenance_mismatches:
            self.dependencies.finish_decision_preparation(
                decision_id,
                False,
                "Preparation failed provenance verification; orphan/mismatched resource request detected.",
            )
            raise PreparationError(
                status_code=502,
                detail="Preparation created a resource request without the expected decision provenance. Preparation was marked failed; do not fulfill the orphan request.",
            )
        pseudo_resource_call = bool(
            re.search(
                '(?is)(?:"name"\\s*:\\s*"propose_resource_request"|\\bpropose_resource_request\\s*\\()',
                final_plan,
            )
        )
        pseudo_action_call = bool(
            re.search(
                '(?is)(?:"name"\\s*:\\s*"propose_(?:action|file_operation|browser_action)"|\\bpropose_(?:action|file_operation|browser_action)\\s*\\()',
                final_plan,
            )
        )
        pseudo_tool_call = bool(pseudo_action_call or pseudo_resource_call)
        if pseudo_resource_call and (not (new_actions or new_resource_requests)):
            retry_prompt = (
                preparation_prompt
                + "\n\nCOMPATIBILITY RETRY — YOUR PREVIOUS RESPONSE WAS INVALID. You printed propose_resource_request JSON instead of invoking the tool. Do not print any function-call JSON. Invoke propose_resource_request NOW for each genuinely blocking resource. For access/credential/plugin/data/service/hardware/other requests, omit amount and currency entirely. For an unknown budget amount, also omit amount and currency. After the real tool call succeeds, summarize the created request IDs in prose."
            )
            meeting_result = self._run_preparation_meeting(retry_prompt)
            participants = meeting_result.get("participants", [])
            final_plan = meeting_result.get("final_decision", "")
            (
                proposed_action_ids,
                proposed_resource_request_ids,
                new_actions,
                new_resource_requests,
            ) = self._load_created_items(meeting_result)
            retry_action_mismatch, retry_resource_mismatch = (
                self._provenance_mismatches(
                    proposed_action_ids,
                    proposed_resource_request_ids,
                    new_actions,
                    new_resource_requests,
                )
            )
            if retry_action_mismatch or retry_resource_mismatch:
                self.dependencies.finish_decision_preparation(
                    decision_id,
                    False,
                    "Resource compatibility retry failed provenance verification.",
                )
                raise PreparationError(
                    status_code=502,
                    detail="Resource compatibility retry created mismatched provenance.",
                )
            pseudo_resource_call = bool(
                re.search(
                    '(?is)(?:"name"\\s*:\\s*"propose_resource_request"|\\bpropose_resource_request\\s*\\()',
                    final_plan,
                )
            )
            pseudo_action_call = bool(
                re.search(
                    '(?is)(?:"name"\\s*:\\s*"propose_(?:action|file_operation|browser_action)"|\\bpropose_(?:action|file_operation|browser_action)\\s*\\()',
                    final_plan,
                )
            )
            pseudo_tool_call = bool(pseudo_action_call or pseudo_resource_call)
        if pseudo_resource_call and (not new_resource_requests):
            materialized_resource_ids = self._materialize_resource_requests_from_text(
                final_plan
            )
            if materialized_resource_ids:
                proposed_resource_request_ids = materialized_resource_ids
                new_resource_requests = [
                    resource_request
                    for request_id in materialized_resource_ids
                    if (
                        resource_request := self.dependencies.get_resource_request_by_id(
                            request_id
                        )
                    )
                    is not None
                ]
                _, resource_provenance_mismatches = self._provenance_mismatches(
                    [], proposed_resource_request_ids, [], new_resource_requests
                )
                if resource_provenance_mismatches:
                    self.dependencies.finish_decision_preparation(
                        decision_id,
                        False,
                        "Materialized resource request failed provenance verification.",
                    )
                    raise PreparationError(
                        status_code=502,
                        detail="Materialized resource request had invalid decision provenance. Preparation was marked failed.",
                    )
                pseudo_resource_call = False
        if (
            pseudo_action_call
            and (not new_actions)
            or (pseudo_resource_call and (not new_resource_requests))
        ):
            self.dependencies.finish_decision_preparation(
                decision_id,
                False,
                "Preparation failed verification: an executive printed a tool-call imitation but no matching real proposal/request was created.",
            )
            raise PreparationError(
                status_code=502,
                detail="Preparation agent described/printed a propose_* tool call without actually invoking the tool. No matching proposal/request was created, so preparation was marked failed and is safe to retry.",
            )
        return (meeting_result, final_plan, participants)

    def _build_prompt(self, decision, goal):
        """Direction guides preparation; only the original task supplies evidence."""
        decision_id = self.decision_id
        return (
            f"PHASE 2 — PREPARATION FOR APPROVED DECISION #{decision_id}\n\n"
            f"Original topic: {decision['topic']}\n\n"
            f"Original evidence/task:\n{decision['task_description']}\n\n"
            f"Human-approved strategic direction:\n{decision['decision_outcome']}\n\n"
            + (
                f"Linked company goal: {goal['title']}\n"
                f"Goal success criteria: {goal['success_criteria']}\n"
                f"Goal priority: {goal['priority']}\n"
                f"Goal target date: {goal.get('target_date') or 'none'}\n\n"
                if goal
                else ""
            )
            + "Your job is NOT to re-decide whether the direction should happen. "
            "Translate the approved direction into a concrete, safe preparation plan. "
            "Identify required resources, access, credentials, plugins, data, files, "
            "browser steps, or commands. If a concrete action is genuinely needed and "
            "your role has an appropriate propose_* tool, you MAY propose it for human "
            "review. IMPORTANT: if you decide a proposal is needed, CALL the actual tool. "
            "Do not print, imitate, or describe a JSON/function-call payload in your answer. "
            "A textual pseudo-call is invalid and will fail preparation verification. "
            "Never claim a proposed action has executed. For every action you actually "
            "propose, include an expected_outcome and expected_impact so we can measure "
            "whether it worked later. Include expected_cost_amount + currency ONLY when "
            "the supplied evidence supports a real cost; otherwise leave cost unknown. "
            "Never invent access or credentials we do not have. Never invent a domain or URL. "
            "A browser action may only target an exact URL already present in the trusted "
            "task/evidence, approved decision, or linked goal context; otherwise request the "
            "missing exact URL/resource from the owner. For every missing resource "
            "or capability that genuinely blocks the approved plan, CALL "
            "propose_resource_request so the owner receives a structured request. For a "
            "non-budget request, OMIT amount and currency. For a budget request whose amount "
            "is unknown, OMIT amount and currency — NEVER send strings such as 'Unknown — "
            "evidence required' into numeric/currency fields. Do not put passwords, API keys, "
            "tokens, or secret values in any tool field. Merely listing a missing capability "
            "in prose or printing a JSON object is not a structured request. Minimize actions: "
            "do not propose anything that is not necessary to prepare the approved direction."
        )

    def _run_preparation_meeting(self, task_text: str):
        decision_id = self.decision_id
        decision = self.decision
        allowed_browser_urls = self.allowed_browser_urls
        return self.dependencies.run_executive_meeting(
            workflow_run_id="prepare:"
            + decision["sync_uuid"]
            + ":"
            + hashlib.sha256(task_text.encode()).hexdigest()[:24],
            topic=f"Preparation for Decision #{decision_id}",
            task_description=task_text,
            agent_keys=self.agent_keys,
            agents_source=self.dependencies.agents,
            evidence_text=decision["task_description"],
            provenance_context={
                "decision_id": decision_id,
                "decision_sync_uuid": decision["sync_uuid"],
                "phase": "preparation",
                "allowed_browser_urls": sorted(allowed_browser_urls),
            },
            memory_context={
                "enabled": True,
                "goal_id": decision.get("goal_id"),
                "limit": 5,
            },
            meeting_type="planning",
        )

    def _load_created_items(self, meeting_result: dict):
        action_ids = meeting_result.get("proposed_action_ids", [])
        resource_ids = meeting_result.get("proposed_resource_request_ids", [])
        actions = [
            action
            for action_id in action_ids
            if (action := self.dependencies.get_action_by_id(action_id)) is not None
        ]
        resources = [
            resource
            for request_id in resource_ids
            if (resource := self.dependencies.get_resource_request_by_id(request_id))
            is not None
        ]
        return (action_ids, resource_ids, actions, resources)

    def _provenance_mismatches(self, action_ids, resource_ids, actions, resources):
        decision_id = self.decision_id
        decision = self.decision
        provenance_mismatches = [
            action
            for action in actions
            if action.get("source_decision_id") != decision_id
            or action.get("source_decision_sync_uuid") != decision["sync_uuid"]
            or action.get("source_phase") != "preparation"
        ]
        if len(actions) != len(action_ids):
            provenance_mismatches.append(
                {"error": "Created action ID missing from database"}
            )
        resource_provenance_mismatches = [
            resource
            for resource in resources
            if resource.get("source_decision_id") != decision_id
            or resource.get("source_decision_sync_uuid") != decision["sync_uuid"]
            or resource.get("source_phase") != "preparation"
        ]
        if len(resources) != len(resource_ids):
            resource_provenance_mismatches.append(
                {"error": "Created resource request ID missing from database"}
            )
        return (provenance_mismatches, resource_provenance_mismatches)

    def _extract_resource_request_payloads(self, text: str) -> list[dict]:
        """
        Strictly extracts ONLY printed propose_resource_request dictionaries.
        This fallback exists for models that expose valid tools but print a
        function payload instead of invoking it. Executable action tools are
        deliberately unsupported here.
        """
        allowed_top = {"name", "parameters"}
        allowed_params = {
            "resource_type",
            "resource_name",
            "reason",
            "required_for",
            "amount",
            "currency",
        }
        parsed_payloads: list[dict] = []
        seen: set[tuple] = set()
        for start_index, char in enumerate(text):
            if char != "{":
                continue
            depth = 0
            in_string = False
            escaped = False
            end_index = None
            for idx in range(start_index, len(text)):
                current = text[idx]
                if in_string:
                    if escaped:
                        escaped = False
                    elif current == "\\":
                        escaped = True
                    elif current == '"':
                        in_string = False
                    continue
                if current == '"':
                    in_string = True
                elif current == "{":
                    depth += 1
                elif current == "}":
                    depth -= 1
                    if depth == 0:
                        end_index = idx + 1
                        break
            if end_index is None:
                continue
            candidate = text[start_index:end_index]
            try:
                value = json.loads(candidate)
            except Exception:
                try:
                    value = ast.literal_eval(candidate)
                except Exception:
                    continue
            if (
                not isinstance(value, dict)
                or value.get("name") != "propose_resource_request"
                or set(value.keys()) - allowed_top
            ):
                continue
            params = value.get("parameters")
            if not isinstance(params, dict) or set(params.keys()) - allowed_params:
                continue
            if not {"resource_type", "resource_name", "reason"}.issubset(params):
                continue
            resource_type = params.get("resource_type")
            resource_name = params.get("resource_name")
            reason = params.get("reason")
            required_for = params.get("required_for")
            amount = params.get("amount")
            currency = params.get("currency")
            if not all(
                (
                    isinstance(v, str) and v.strip()
                    for v in (resource_type, resource_name, reason)
                )
            ):
                continue
            if required_for is not None and (not isinstance(required_for, str)):
                continue
            if amount is not None and (not isinstance(amount, (int, float))):
                continue
            if currency is not None and (not isinstance(currency, str)):
                continue
            normalized = {
                "resource_type": resource_type.strip(),
                "resource_name": resource_name.strip(),
                "reason": reason.strip(),
                "required_for": (
                    required_for.strip() if isinstance(required_for, str) else None
                ),
                "amount": amount,
                "currency": currency.strip() if isinstance(currency, str) else None,
            }
            dedupe_key = (
                normalized["resource_type"],
                normalized["resource_name"].lower(),
                normalized["reason"].lower(),
                normalized["required_for"],
                normalized["amount"],
                normalized["currency"],
            )
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                parsed_payloads.append(normalized)
        return parsed_payloads

    def _materialize_resource_requests_from_text(self, text: str) -> list[int]:
        decision_id = self.decision_id
        decision = self.decision
        payloads = self._extract_resource_request_payloads(text)
        if not payloads:
            return []
        created_ids: list[int] = []
        requested_by = (
            self.agent_keys[0].upper() if len(self.agent_keys) == 1 else "PREPARATION"
        )
        # Re-enter trusted provenance only for pending, non-executing requests.
        with self.dependencies.action_provenance_scope(
            decision_id, decision["sync_uuid"], "preparation"
        ):
            for payload in payloads:
                created_ids.append(
                    self.dependencies.propose_resource_request(
                        requested_by=requested_by,
                        resource_type=payload["resource_type"],
                        resource_name=payload["resource_name"],
                        reason=payload["reason"],
                        required_for=payload["required_for"],
                        amount=payload["amount"],
                        currency=payload["currency"],
                    )
                )
        return created_ids
