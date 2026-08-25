"""
Phase 5 — NextQuestionEngine

Determines the next required slot dynamically based on:
1. YAML service specification (required fields list)
2. Already filled slots (session.filled_slots)
3. OCR-extracted fields (auto-filled from uploaded documents)
4. Validation status of filled fields

This engine eliminates hardcoded conversation flows.
The conversation adapts to what the citizen has already provided.

Example: If Aadhaar OCR already extracted name, DOB, and address,
the engine skips those and asks only for remaining fields (income, occupation, etc.)
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from app.rules_engine.engine import ServiceSpecLoader

logger = logging.getLogger(__name__)


@dataclass
class NextQuestionResult:
    """Result returned by NextQuestionEngine.get_next_slot()"""
    has_next: bool                      # True if there is a remaining required slot
    slot_name: Optional[str] = None     # Field name to ask next
    slot_spec: Optional[Dict] = None    # Full slot spec from YAML (for LLM prompt generation)
    filled_count: int = 0               # Number of slots already filled
    total_required: int = 0             # Total number of required slots
    completion_percentage: float = 0.0  # % complete (0-100)
    missing_required: List[str] = field(default_factory=list)    # All still-missing required slots
    optional_missing: List[str] = field(default_factory=list)    # Optional slots not yet filled
    ocr_filled: List[str] = field(default_factory=list)          # Slots auto-filled from OCR
    validation_errors: Dict[str, str] = field(default_factory=dict)  # Field → error message

    @property
    def missing_slots(self) -> List[str]:
        return self.missing_required


class NextQuestionEngine:
    """
    Determines the next required slot for a given service and conversation state.

    Priority order for slot asking (can be overridden by YAML ordering):
    1. Core identity fields (name, dob, gender)
    2. Contact fields (mobile, email)
    3. Family fields (father, mother)
    4. Address fields (address, district, taluka, village)
    5. Income/occupation fields
    6. Service-specific fields (purpose, family_count, etc.)
    """

    # Default priority order when YAML doesn't specify ordering
    DEFAULT_PRIORITY = [
        "applicant_name",
        "applicant_dob",
        "gender",
        "mobile_number",
        "email",
        "father_name",
        "mother_name",
        "aadhaar_number",
        "address",
        "district",
        "taluka",
        "village",
        "occupation",
        "annual_income",
        "family_member_count",
        "earning_family_members",
        "annual_family_income",
        "purpose",
    ]

    def get_next_slot(
        self,
        service_id: str,
        filled_slots: Dict[str, Any],
        ocr_fields: Optional[Dict[str, Any]] = None,
        validation_errors: Optional[Dict[str, str]] = None,
    ) -> NextQuestionResult:
        """
        Calculate which slot to ask next.

        Args:
            service_id: e.g., 'income_certificate'
            filled_slots: Dict of already-filled {field_name: value}
            ocr_fields: Dict of fields auto-extracted from uploaded documents
            validation_errors: Dict of {field_name: error_message} for invalid values

        Returns:
            NextQuestionResult with has_next, slot_name, slot_spec, completion info
        """
        try:
            spec = ServiceSpecLoader.get(service_id)
        except Exception as e:
            logger.error(f"Failed to load service spec for {service_id}: {e}")
            return NextQuestionResult(has_next=False, completion_percentage=100.0)

        # All known values = filled by citizen + extracted by OCR
        ocr_fields = ocr_fields or {}
        validation_errors = validation_errors or {}
        all_known = {**ocr_fields, **filled_slots}  # filled_slots overrides OCR (citizen's choice)

        # Get all slots from YAML spec
        all_slots = getattr(spec, "slots", None) or getattr(spec, "fields", None) or []
        if not all_slots:
            logger.warning(f"Service {service_id} has no slots/fields defined in YAML")
            return NextQuestionResult(has_next=False, completion_percentage=100.0)

        # Separate required vs optional
        required_slots = []
        optional_slots = []
        for slot in all_slots:
            slot_dict = self._slot_to_dict(slot)
            if slot_dict.get("required", True):
                required_slots.append(slot_dict)
            else:
                optional_slots.append(slot_dict)

        total_required = len(required_slots)

        # Find missing required slots (not filled, not in OCR, or has validation error)
        missing_required = []
        ocr_filled = []

        for slot_dict in required_slots:
            name = slot_dict["name"]
            value = all_known.get(name)

            if name in ocr_fields and name not in filled_slots:
                # Auto-filled from OCR — count as filled unless it has a validation error
                if name not in validation_errors:
                    ocr_filled.append(name)
                    continue
                else:
                    missing_required.append(slot_dict)
            elif value is not None and name not in validation_errors:
                continue  # Already filled and valid
            else:
                missing_required.append(slot_dict)

        # Find missing optional slots
        optional_missing = [
            s["name"] for s in optional_slots
            if all_known.get(s["name"]) is None
        ]

        # Count filled required slots
        filled_required_count = total_required - len(missing_required)
        completion_pct = (filled_required_count / total_required * 100) if total_required > 0 else 100.0

        if not missing_required:
            return NextQuestionResult(
                has_next=False,
                filled_count=filled_required_count,
                total_required=total_required,
                completion_percentage=100.0,
                ocr_filled=ocr_filled,
                optional_missing=optional_missing,
                validation_errors=validation_errors,
            )

        # Sort missing by priority order
        missing_required.sort(key=lambda s: self._priority(s["name"]))

        next_slot = missing_required[0]

        return NextQuestionResult(
            has_next=True,
            slot_name=next_slot["name"],
            slot_spec=next_slot,
            filled_count=filled_required_count,
            total_required=total_required,
            completion_percentage=round(completion_pct, 1),
            missing_required=[s["name"] for s in missing_required],
            optional_missing=optional_missing,
            ocr_filled=ocr_filled,
            validation_errors=validation_errors,
        )

    def _slot_to_dict(self, slot) -> Dict:
        """Convert slot object (or dict) to a consistent dict."""
        if isinstance(slot, dict):
            return slot
        # Pydantic model or dataclass
        result = {}
        for key in ["name", "type", "required", "classification", "validation", "prompt", "options"]:
            val = getattr(slot, key, None)
            if val is not None:
                result[key] = val if not hasattr(val, "dict") else val.dict()
        if "name" not in result:
            result["name"] = str(slot)
        result.setdefault("required", True)
        return result

    def _priority(self, slot_name: str) -> int:
        """Return sort priority (lower = asked sooner)."""
        try:
            return self.DEFAULT_PRIORITY.index(slot_name)
        except ValueError:
            return 999  # Unknown fields asked last
