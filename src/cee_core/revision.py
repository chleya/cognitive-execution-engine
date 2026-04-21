"""ModelRevisionEvent: explicit model revision after reality contact.

When reality contact returns results that differ from the internal world model,
a ModelRevisionEvent records exactly what changed, why, and what evidence
justified the change. This is the second core object of the CEE layer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal, Tuple

from .commitment import CommitmentEvent
from .world_schema import RevisionDelta, WorldHypothesis
from .world_state import (
    WorldState,
    add_anchor_facts,
    update_hypothesis_status,
)

REVISION_SCHEMA_VERSION = "cee.revision.v1"

RevisionKind = Literal[
    "confirmation",
    "correction",
    "expansion",
    "compression",
    "recalibration",
]


@dataclass(frozen=True)
class ModelRevisionEvent:
    revision_id: str
    prior_state_id: str
    caused_by_event_id: str

    revision_kind: RevisionKind

    deltas: Tuple[RevisionDelta, ...] = ()

    discarded_hypothesis_ids: Tuple[str, ...] = ()
    strengthened_hypothesis_ids: Tuple[str, ...] = ()
    new_anchor_fact_summaries: Tuple[str, ...] = ()

    resulting_state_id: str = ""
    revision_summary: str = ""

    event_type: str = "revision"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REVISION_SCHEMA_VERSION,
            "event_type": "revision",
            "revision_id": self.revision_id,
            "prior_state_id": self.prior_state_id,
            "caused_by_event_id": self.caused_by_event_id,
            "revision_kind": self.revision_kind,
            "deltas": [d.to_dict() for d in self.deltas],
            "discarded_hypothesis_ids": list(self.discarded_hypothesis_ids),
            "strengthened_hypothesis_ids": list(self.strengthened_hypothesis_ids),
            "new_anchor_fact_summaries": list(self.new_anchor_fact_summaries),
            "resulting_state_id": self.resulting_state_id,
            "revision_summary": self.revision_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelRevisionEvent:
        return cls(
            revision_id=payload["revision_id"],
            prior_state_id=payload["prior_state_id"],
            caused_by_event_id=payload["caused_by_event_id"],
            revision_kind=payload["revision_kind"],
            deltas=tuple(RevisionDelta.from_dict(d) for d in payload.get("deltas", [])),
            discarded_hypothesis_ids=tuple(payload.get("discarded_hypothesis_ids", ())),
            strengthened_hypothesis_ids=tuple(payload.get("strengthened_hypothesis_ids", ())),
            new_anchor_fact_summaries=tuple(payload.get("new_anchor_fact_summaries", ())),
            resulting_state_id=payload.get("resulting_state_id", ""),
            revision_summary=payload.get("revision_summary", ""),
        )


def revise_from_commitment(
    state: WorldState,
    event: CommitmentEvent,
    *,
    revision_id: str,
    resulting_state_id: str,
    strengthened_hypothesis_ids: Tuple[str, ...] = (),
    discarded_hypothesis_ids: Tuple[str, ...] = (),
    new_anchor_fact_summaries: Tuple[str, ...] = (),
    revision_summary: str = "",
) -> Tuple[ModelRevisionEvent, WorldState]:
    deltas: list[RevisionDelta] = []

    for fact in new_anchor_fact_summaries:
        deltas.append(RevisionDelta(
            delta_id=f"delta-anchor-{len(deltas) + 1}",
            target_kind="anchor_add",
            target_ref=fact,
            before_summary="fact not anchored",
            after_summary=fact,
            justification=f"anchored by event {event.event_id}",
        ))

    for hid in strengthened_hypothesis_ids:
        deltas.append(RevisionDelta(
            delta_id=f"delta-hyp-strengthen-{hid}",
            target_kind="hypothesis_update",
            target_ref=hid,
            before_summary="hypothesis tentative/uncertain",
            after_summary="hypothesis strengthened",
            justification=f"supported by event {event.event_id}",
        ))

    for hid in discarded_hypothesis_ids:
        deltas.append(RevisionDelta(
            delta_id=f"delta-hyp-discard-{hid}",
            target_kind="hypothesis_remove",
            target_ref=hid,
            before_summary="hypothesis active/tentative",
            after_summary="hypothesis rejected",
            justification=f"contradicted by event {event.event_id}",
        ))

    revision_kind: RevisionKind = "confirmation"
    if discarded_hypothesis_ids:
        revision_kind = "correction"
    elif new_anchor_fact_summaries and not discarded_hypothesis_ids:
        revision_kind = "expansion"

    revision_event = ModelRevisionEvent(
        revision_id=revision_id,
        prior_state_id=state.state_id,
        caused_by_event_id=event.event_id,
        revision_kind=revision_kind,
        deltas=tuple(deltas),
        discarded_hypothesis_ids=discarded_hypothesis_ids,
        strengthened_hypothesis_ids=strengthened_hypothesis_ids,
        new_anchor_fact_summaries=new_anchor_fact_summaries,
        resulting_state_id=resulting_state_id,
        revision_summary=revision_summary,
    )

    new_state = state
    provenance = f"revision:{revision_id}"

    for hid in discarded_hypothesis_ids:
        new_state = update_hypothesis_status(
            new_state, hid, "rejected", 0.0, provenance_ref=provenance,
        )

    for hid in strengthened_hypothesis_ids:
        h = new_state.find_hypothesis(hid)
        new_conf = min(1.0, (h.confidence if h else 0.5) + 0.2)
        new_state = update_hypothesis_status(
            new_state, hid, "active", new_conf, provenance_ref=provenance,
        )

    if new_anchor_fact_summaries:
        new_state = add_anchor_facts(
            new_state, new_anchor_fact_summaries, provenance_ref=provenance,
        )

    new_state = replace(new_state, state_id=resulting_state_id)

    return revision_event, new_state
