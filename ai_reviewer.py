from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from openai import OpenAI

log = logging.getLogger("ai_reviewer")


class AIReviewer:
    """Fail-closed AI reviewer. AI may approve/reject/wait, but cannot invent levels."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.client = OpenAI(api_key=cfg.openai_api_key) if cfg.openai_api_key else None

    def review(self, signal, context: dict[str, Any]) -> tuple[bool, str, str]:
        if self.cfg.ai_mode == "OFF":
            return True, "LOCAL_APPROVAL", "AI review disabled"
        if self.client is None:
            return False, "REJECT", "OPENAI_API_KEY missing"

        payload = {
            "candidate": asdict(signal),
            "context": context,
            "rules": {
                "allowed_decisions": ["APPROVE", "REJECT", "WAIT"],
                "must_not_change_prices": True,
                "minimum_score": self.cfg.minimum_candidate_score,
                "goal": "Approve only clear external 1H structure with a high-quality 15m swing candidate aligned with EMA trend and Fibonacci retracement.",
            },
        }
        schema = {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": ["APPROVE", "REJECT", "WAIT"]},
                "selected_candidate_id": {"type": "string"},
                "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                "reason": {"type": "string"},
            },
            "required": ["decision", "selected_candidate_id", "confidence", "reason"],
            "additionalProperties": False,
        }
        try:
            response = self.client.responses.create(
                model=self.cfg.openai_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a conservative crypto swing reviewer. Review only the supplied candidate. "
                            "Never invent or alter entry, stop, target, swing prices or times. Reject ambiguous, "
                            "internal, weak or late setups. Return structured JSON only."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, default=str)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "swing_review",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
            data = json.loads(response.output_text)
            decision = str(data["decision"]).upper()
            candidate_ok = data["selected_candidate_id"] == signal.candidate_id
            confidence = int(data["confidence"])
            approved = decision == "APPROVE" and candidate_ok and confidence >= self.cfg.ai_min_confidence
            return approved, decision, str(data["reason"])
        except Exception as exc:
            log.exception("AI REVIEW ERROR")
            return False, "REJECT", f"AI service failure: {exc}"
