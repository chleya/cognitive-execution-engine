"""Audit payload policy helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal


CompilerAuditMode = Literal["plain", "hash", "omit"]


@dataclass(frozen=True)
class CompilerAuditPolicy:
    """Controls how raw compiler input is recorded in audit events."""

    mode: CompilerAuditMode = "hash"

    def raw_input_payload(self, raw_input: str) -> dict[str, object]:
        if self.mode == "plain":
            return {"raw_input": raw_input, "raw_input_audit_mode": "plain"}

        if self.mode == "hash":
            digest = hashlib.sha256(raw_input.encode("utf-8")).hexdigest()
            return {
                "raw_input_sha256": digest,
                "raw_input_length": len(raw_input),
                "raw_input_audit_mode": "hash",
            }

        if self.mode == "omit":
            return {"raw_input_audit_mode": "omit"}

        raise ValueError(f"Unsupported compiler audit mode: {self.mode}")

