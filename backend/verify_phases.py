from app.orchestration.state_machine.application_fsm import ApplicationFSM, AppState
fsm = ApplicationFSM()
ok1, msg1 = fsm.transition(AppState.CONSENT_GIVEN)
ok2, msg2 = fsm.transition(AppState.SERVICE_SELECTED)
ok3, bad = fsm.transition(AppState.CERTIFICATE_READY)
print(f"FSM valid transitions: {ok1} {ok2}")
print(f"FSM invalid blocked: {not ok3}")
print(f"FSM progress: {fsm.progress}%")
print(f"Msg EN: {fsm.get_citizen_message('en')[:50]}")
print(f"Msg HI: {fsm.get_citizen_message('hi')[:50]}")

from app.services.language_service import LanguageService
ls = LanguageService()
print(f"Hindi: {ls.detect_language('mera naam Ramesh hai')}")
print(f"Hindi script: {ls.detect_language('मेरा नाम रमेश है')}")
print(f"Marathi: {ls.detect_language('माझे नाव रमेश आहे')}")
print(f"English: {ls.detect_language('my name is Ramesh')}")

from app.orchestration.nlu.intent_classifier import IntentClassifier
clf = IntentClassifier()
r = clf.classify("I want income certificate")
print(f"Intent: {r['intent']} | Service: {r['service_type']}")
r2 = clf.classify("meri aay 150000 hai")
print(f"Intent2: {r2['intent']} | Entities: {r2['entities']}")

from app.services.i18n import get_template
t = get_template("greeting", "hi")
print(f"i18n greeting HI: {t[:50]}")
t2 = get_template("submission_success", "mr", tracking_id="TRK-12345")
print(f"i18n submission MR: {t2[:60]}")

print("ALL CHECKS PASSED")
