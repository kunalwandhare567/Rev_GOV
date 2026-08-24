"""
Business & Rules Engine
Loads declarative YAML service specs and evaluates rules.
Adding a new service = adding one YAML file. No new code.
"""
import os
import re
import yaml
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SlotSpec:
    name: str
    type: str
    required: bool
    classification: str  # RESTRICTED | QUASI_IDENTIFIER | NON_SENSITIVE
    validation: Dict[str, Any]
    prompt: Dict[str, str]  # {lang: prompt_text}


@dataclass
class FeeResult:
    base_fee: float
    discount: float
    final_fee: float
    waiver_reason: Optional[str] = None


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ServiceSpec:
    id: str
    name: Dict[str, str]
    department: str
    sla_days: int
    fee_amount: float
    fee_currency: str
    waiver_conditions: List[Dict]
    slots: List[SlotSpec]
    required_docs: List[Dict]
    optional_docs: List[Dict]
    eligibility_rules: List[Dict]
    cross_field_validations: List[Dict]


class ServiceSpecLoader:
    """Loads and caches all YAML service specs from the specs directory."""

    _cache: Dict[str, ServiceSpec] = {}

    @classmethod
    def load_all(cls) -> Dict[str, ServiceSpec]:
        """Load all YAML specs from the service_specs directory."""
        if cls._cache:
            return cls._cache

        specs_dir = settings.SERVICE_SPECS_DIR
        if not os.path.exists(specs_dir):
            logger.warning(f"Service specs directory not found: {specs_dir}")
            return {}

        for filename in os.listdir(specs_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(specs_dir, filename)
                try:
                    spec = cls._load_file(filepath)
                    cls._cache[spec.id] = spec
                    logger.info(f"Loaded service spec: {spec.id}")
                except Exception as e:
                    logger.error(f"Failed to load spec {filename}: {e}")

        return cls._cache

    @classmethod
    def get(cls, service_id: str) -> Optional[ServiceSpec]:
        """Get a specific service spec by ID."""
        if not cls._cache:
            cls.load_all()
        return cls._cache.get(service_id)

    @classmethod
    def list_services(cls) -> List[Dict]:
        """List all available services (for catalogue endpoint)."""
        if not cls._cache:
            cls.load_all()
        return [
            {
                "id": spec.id,
                "name": spec.name,
                "department": spec.department,
                "sla_days": spec.sla_days,
                "fee_amount": spec.fee_amount,
                "fee_currency": spec.fee_currency,
            }
            for spec in cls._cache.values()
        ]

    @classmethod
    def _load_file(cls, filepath: str) -> ServiceSpec:
        """Parse a YAML file into a ServiceSpec object."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        svc = data["service"]
        slots = [
            SlotSpec(
                name=s["name"],
                type=s.get("type", "string"),
                required=s.get("required", True),
                classification=s.get("classification", "NON_SENSITIVE"),
                validation=s.get("validation", {}),
                prompt=s.get("prompt", {}),
            )
            for s in data.get("slots", [])
        ]

        docs = data.get("documents", {})
        required_docs = docs.get("required", [])
        optional_docs = docs.get("optional", [])

        return ServiceSpec(
            id=svc["id"],
            name=svc.get("name", {}),
            department=svc.get("department", "Revenue Department"),
            sla_days=svc.get("sla_days", 7),
            fee_amount=svc.get("fee", {}).get("amount", 0),
            fee_currency=svc.get("fee", {}).get("currency", "INR"),
            waiver_conditions=svc.get("fee", {}).get("waiver_conditions", []),
            slots=slots,
            required_docs=required_docs,
            optional_docs=optional_docs,
            eligibility_rules=data.get("eligibility", []),
            cross_field_validations=data.get("cross_field_validations", []),
        )


class FieldValidator:
    """
    Validates individual form field values against slot spec rules.
    All validation is deterministic — no LLM involved.
    """

    @classmethod
    def validate_slot(cls, slot: SlotSpec, value: Any, language: str = "en") -> Tuple[bool, str]:
        """
        Returns (is_valid, error_message).
        """
        v = slot.validation

        if value is None or (isinstance(value, str) and value.strip() == ""):
            if slot.required:
                return False, f"'{slot.name}' is required"
            return True, ""

        value_str = str(value).strip()

        # Type coercion and validation
        if slot.type == "number":
            try:
                num = float(value_str.replace(",", ""))
                if "min" in v and num < v["min"]:
                    return False, v.get("error_msg", f"Value must be at least {v['min']}")
                if "max" in v and num > v["max"]:
                    return False, v.get("error_msg", f"Value must be at most {v['max']}")
            except ValueError:
                return False, f"'{slot.name}' must be a number"

        if slot.type == "string":
            # Prevent service titles from being stored as applicant names
            if slot.name in ("applicant_name", "full_name", "name"):
                v_lower = value_str.lower()
                invalid_names = ["income certificate", "caste certificate", "domicile certificate", "obc certificate", "certificate", "income", "caste", "domicile"]
                if v_lower in invalid_names or "certificate" in v_lower:
                    return False, "Please enter a valid person's full name, not a service name."

            if "min_length" in v and len(value_str) < v["min_length"]:
                return False, f"'{slot.name}' must be at least {v['min_length']} characters"
            if "max_length" in v and len(value_str) > v["max_length"]:
                return False, f"'{slot.name}' must not exceed {v['max_length']} characters"
            if "pattern" in v:
                if not re.match(v["pattern"], value_str):
                    return False, v.get("error_msg", f"'{slot.name}' format is invalid")
            if "allowed_values" in v and value_str.upper() not in [av.upper() for av in v["allowed_values"]]:
                return False, f"'{slot.name}' must be one of: {', '.join(v['allowed_values'])}"

        if slot.type == "date":
            # Validate date format DD-MM-YYYY
            date_pattern = r"^\d{2}-\d{2}-\d{4}$"
            if not re.match(date_pattern, value_str):
                return False, f"'{slot.name}' must be in DD-MM-YYYY format"

        return True, ""


class EligibilityChecker:
    """
    Evaluates eligibility rules from the service spec.
    Uses safe expression evaluation — no arbitrary code execution.
    """

    SAFE_OPERATORS = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        "==": lambda a, b: str(a).upper() == str(b).upper(),
        "!=": lambda a, b: str(a).upper() != str(b).upper(),
        "in": lambda a, b: str(a).upper() in [str(x).upper() for x in b] if isinstance(b, list) else str(a) in str(b),
    }

    @classmethod
    def check(cls, spec: ServiceSpec, filled_slots: Dict, language: str = "en") -> ValidationResult:
        """Check all eligibility rules against filled slot data."""
        errors = []

        for rule in spec.eligibility_rules:
            rule_str = rule.get("rule", "")
            error_msg = rule.get("error", {}).get(language, rule.get("error", {}).get("en", "Eligibility check failed"))

            try:
                if not cls._evaluate_rule(rule_str, filled_slots):
                    errors.append(error_msg)
            except Exception as e:
                logger.warning(f"Could not evaluate rule '{rule_str}': {e}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @classmethod
    def _evaluate_rule(cls, rule_str: str, data: Dict) -> bool:
        """Safely evaluate a simple eligibility rule string."""
        # Handle applicant_age computed from dob
        if "applicant_age" in rule_str and "applicant_dob" in data:
            import datetime
            try:
                dob_parts = data["applicant_dob"].split("-")
                if len(dob_parts) == 3:
                    dob = datetime.date(int(dob_parts[2]), int(dob_parts[1]), int(dob_parts[0]))
                    today = datetime.date.today()
                    age = (today - dob).days // 365
                    data = {**data, "applicant_age": age}
            except Exception:
                data = {**data, "applicant_age": 25}  # Default safe age if parse fails

        # Parse simple comparison rules: "field OPERATOR value"
        for op, func in sorted(cls.SAFE_OPERATORS.items(), key=lambda x: -len(x[0])):
            if f" {op} " in rule_str:
                parts = rule_str.split(f" {op} ", 1)
                left_key = parts[0].strip()
                right_raw = parts[1].strip().strip("'\"")

                left_val = data.get(left_key)
                if left_val is None:
                    return True  # Can't evaluate without the field

                # Try numeric comparison
                try:
                    left_num = float(str(left_val).replace(",", ""))
                    right_num = float(right_raw.replace(",", ""))
                    return func(left_num, right_num)
                except (ValueError, TypeError):
                    pass

                # List membership check
                if op == "in" and right_raw.startswith("["):
                    import ast
                    right_list = ast.literal_eval(right_raw)
                    return func(left_val, right_list)

                return func(str(left_val), str(right_raw))

        return True  # Unknown rule: pass


class FeeCalculator:
    """
    Calculates fees and waivers based on service spec and citizen data.
    Config-driven: no fee amounts hardcoded in Python.
    """

    @classmethod
    def calculate(cls, spec: ServiceSpec, citizen_data: Dict) -> FeeResult:
        """Calculate final fee after applying any eligible waivers."""
        base_fee = spec.fee_amount

        for waiver in spec.waiver_conditions:
            condition = waiver.get("condition", "")
            waiver_percent = waiver.get("waiver_percent", 0)

            try:
                if cls._evaluate_condition(condition, citizen_data):
                    discount = base_fee * (waiver_percent / 100)
                    return FeeResult(
                        base_fee=base_fee,
                        discount=discount,
                        final_fee=max(0.0, base_fee - discount),
                        waiver_reason=condition,
                    )
            except Exception as e:
                logger.debug(f"Waiver condition eval error: {e}")

        return FeeResult(base_fee=base_fee, discount=0.0, final_fee=base_fee)

    @classmethod
    def _evaluate_condition(cls, condition: str, data: Dict) -> bool:
        """Evaluate a simple condition string against citizen data."""
        # Handle: field < value, field > value, field == True/False
        for op in ["<=", ">=", "==", "<", ">"]:
            if f" {op} " in condition:
                parts = condition.split(f" {op} ", 1)
                left_key = parts[0].strip()
                right_raw = parts[1].strip()
                left_val = data.get(left_key)

                if left_val is None:
                    return False

                if right_raw in ("True", "False"):
                    right_val = right_raw == "True"
                    return {
                        "==": lambda a, b: a == b,
                        "!=": lambda a, b: a != b,
                    }.get(op, lambda a, b: False)(left_val, right_val)

                try:
                    return {
                        "<": lambda a, b: a < b,
                        ">": lambda a, b: a > b,
                        "<=": lambda a, b: a <= b,
                        ">=": lambda a, b: a >= b,
                        "==": lambda a, b: a == b,
                    }[op](float(str(left_val).replace(",", "")), float(right_raw))
                except (ValueError, TypeError):
                    return False
        return False
