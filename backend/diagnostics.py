"""System diagnostic script"""
import sys
print(f"Python: {sys.version.split()[0]}")

# 1. Config
from app.core.config import settings
print(f"[OK] Config: DB={settings.DATABASE_URL}")

# 2. Database + all tables
from app.core.database import engine, Base
from app.models.db_models import (
    User, Citizen, Service, Application, ApplicationData,
    Document, Payment, ConversationSession, ConversationMessage,
    Escalation, Certificate, AuditLog
)
Base.metadata.create_all(bind=engine)
print("[OK] All DB tables created/verified")

# 3. Service specs loaded
from app.rules_engine.engine import ServiceSpecLoader
specs = ServiceSpecLoader.load_all()
print(f"[OK] Service specs: {list(specs.keys())}")

# 4. Data Guard
from app.data_guard.guard import DataGuard, DataClassifier, DataGuardBlockedError
guard = DataGuard(audit_logger=None)
restricted, quasi = DataClassifier.scan_payload({"applicant_name": "Test"})
assert "applicant_name" in restricted
print("[OK] Data Guard: PII detection working")

# Guard blocks PII
try:
    guard.check(
        payload={"applicant_name": "Ramesh Kumar", "msg": "hello"},
        destination="cloud_llm", caller="test", operation="translate"
    )
    print("[FAIL] Data Guard should have blocked!")
except DataGuardBlockedError as e:
    print(f"[OK] Data Guard BLOCKS PII correctly: {e.blocked_fields}")

# Guard allows safe payload
result = guard.check(
    payload={"message": "translate income certificate to Hindi"},
    destination="cloud_llm", caller="test", operation="translate"
)
assert result.allowed
print("[OK] Data Guard ALLOWS clean payloads")

# 5. Field encryption
from app.data_layer.encryption import FieldEncryptor
enc = FieldEncryptor.encrypt("123456789012")
dec = FieldEncryptor.decrypt(enc)
assert dec == "123456789012"
print("[OK] AES-256-GCM encryption/decryption working")

# 6. Fraud scorer
from app.rules_engine.fraud_scorer import FraudScorer
score, feats, decision = FraudScorer.score({"resubmission_count_1h": 0, "correction_count": 0})
assert decision == "PASS"
print(f"[OK] Fraud scorer: score={score}, decision={decision}")

# High-risk scenario
score2, feats2, decision2 = FraudScorer.score({
    "resubmission_count_1h": 5,
    "field_mismatch_rate": 0.8,
    "application_hour": 3
})
assert decision2 in ("MANUAL_REVIEW", "REJECT")
print(f"[OK] Fraud scorer HIGH RISK: score={score2}, decision={decision2}")

# 7. Fee calculator with waiver
from app.rules_engine.engine import FeeCalculator
spec = ServiceSpecLoader.get("income_certificate")
fee = FeeCalculator.calculate(spec, {"annual_income": 15000})
assert fee.final_fee == 0.0
print(f"[OK] Fee calculator: 100% waiver for low income. Final=INR {fee.final_fee}")

fee2 = FeeCalculator.calculate(spec, {"annual_income": 500000})
assert fee2.final_fee == 50.0
print(f"[OK] Fee calculator: Standard fee. Final=INR {fee2.final_fee}")

# OBC NCL income limit
spec_ncl = ServiceSpecLoader.get("obc_ncl_certificate")
from app.rules_engine.engine import EligibilityChecker
check = EligibilityChecker.check(spec_ncl, {
    "applicant_dob": "01-01-1990",
    "annual_income": 900000,
    "caste_category": "OBC"
})
assert not check.valid
print("[OK] OBC-NCL eligibility: blocks income > 8 lakh correctly")

# Domicile 15-year rule
spec_dom = ServiceSpecLoader.get("domicile_certificate")
check2 = EligibilityChecker.check(spec_dom, {
    "applicant_dob": "01-01-1990",
    "residence_years": 10
})
assert not check2.valid
print("[OK] Domicile eligibility: blocks < 15 years residence correctly")

# 8. Session & citizen repo
from app.core.database import SessionLocal
from app.data_layer.repositories.citizen_repo import CitizenRepository
from app.data_layer.repositories.session_repo import SessionRepository
db = SessionLocal()
citizen = CitizenRepository(db).resolve_or_create("test_diag_user_xyz")
assert len(citizen.citizen_ref) == 32  # HMAC-SHA256 token
print(f"[OK] Citizen tokenization: ref={citizen.citizen_ref[:16]}...")

session = SessionRepository(db).create_session(citizen.citizen_ref, "WEB", "en")
print(f"[OK] Context Vault: session created at node={session.current_node}")
db.close()

# 9. NLU keyword fallback
from app.orchestration.nlu.local_llm import LocalNLU
nlu = LocalNLU()
r = nlu._analyze_with_keywords("I need an income certificate", "en")
assert r["intent"] == "CERTIFICATE_REQUEST"
assert r["service_type"] == "income_certificate"
print(f"[OK] NLU: intent={r['intent']}, service={r['service_type']}")

r2 = nlu._analyze_with_keywords("what is the status of my application", "en")
assert r2["intent"] == "STATUS_QUERY"
print(f"[OK] NLU: status query detected correctly")

r3 = nlu._analyze_with_keywords("mujhe aay praman patra chahiye", "hi")
assert r3["intent"] == "CERTIFICATE_REQUEST"
print(f"[OK] NLU: Hindi intent detected")

print()
print("=" * 55)
print("  ALL SYSTEMS OPERATIONAL - BACKEND READY")
print("=" * 55)
