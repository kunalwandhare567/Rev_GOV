"""
Phase 6 — i18n Notification Templates (13 Indian Languages)
Used by:
  - WhatsApp chat responses
  - IVR voice prompts
  - SMS notifications
  - In-app status messages

All strings are parameterized with {tracking_id}, {status}, etc.
"""
from typing import Dict, Optional


# ── Base Template Keys ─────────────────────────────────────────────────────

TEMPLATES: Dict[str, Dict[str, str]] = {

    # ── Greetings ──────────────────────────────────────────────────────────
    "greeting": {
        "en": "Hello! Welcome to RevenueSeva — Government Certificate Services. 🙏\nHow can I help you today?",
        "hi": "नमस्ते! RevenueSeva में आपका स्वागत है — सरकारी प्रमाण पत्र सेवाएं। 🙏\nमैं आज आपकी कैसे मदद कर सकता हूँ?",
        "mr": "नमस्कार! RevenueSeva मध्ये स्वागत आहे — सरकारी प्रमाणपत्र सेवा. 🙏\nआज मी तुम्हाला कशी मदत करू?",
        "gu": "નમસ્તે! RevenueSeva માં આપનું સ્વાગત છે. 🙏",
        "te": "నమస్కారం! RevenueSeva కి స్వాగతం. 🙏",
        "ta": "வணக்கம்! RevenueSeva-க்கு வரவேற்கிறோம். 🙏",
        "kn": "ನಮಸ್ಕಾರ! RevenueSeva ಗೆ ಸ್ವಾಗತ. 🙏",
        "ml": "നമസ്കാരം! RevenueSeva-ലേക്ക് സ്വാഗതം. 🙏",
        "bn": "নমস্কার! RevenueSeva-তে স্বাগতম। 🙏",
        "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! RevenueSeva ਵਿੱਚ ਜੀ ਆਇਆਂ ਨੂੰ। 🙏",
        "ur": "السلام علیکم! RevenueSeva میں خوش آمدید۔ 🙏",
        "or": "ନମସ୍କାର! RevenueSeva ରେ ସ୍ୱାଗତ। 🙏",
        "as": "নমস্কাৰ! RevenueSeva-লৈ স্বাগতম। 🙏",
    },

    # ── Consent Request ────────────────────────────────────────────────────
    "consent_request": {
        "en": "Before we begin, do you consent to share your information with the Revenue Department for the purpose of this certificate application?\n\nReply *YES* to continue or *NO* to cancel.",
        "hi": "शुरू करने से पहले, क्या आप इस प्रमाण पत्र आवेदन के लिए राजस्व विभाग के साथ अपनी जानकारी साझा करने के लिए सहमत हैं?\n\nजारी रखने के लिए *हाँ* या रद्द करने के लिए *नहीं* लिखें।",
        "mr": "सुरू करण्यापूर्वी, या प्रमाणपत्र अर्जासाठी तुम्ही तुमची माहिती महसूल विभागाशी शेअर करण्यास संमती देता का?\n\nपुढे जाण्यासाठी *होय* किंवा रद्द करण्यासाठी *नाही* लिहा.",
        "gu": "શરૂ કરતા પહેલા, શું તમે Revenue વિભાગ સાથે માહિતી શેર કરવા સંમત છો?\n\nચાલુ રાખવા *હા* અથવા રદ્દ કરવા *ના* લખો.",
        "te": "ప్రారంభించే ముందు, Revenue విభాగంతో మీ సమాచారం పంచుకోవడానికి అంగీకరిస్తారా?\n\nకొనసాగించడానికి *అవును* లేదా రద్దు చేయడానికి *లేదు* అని రాయండి.",
        "ta": "தொடங்குவதற்கு முன், Revenue துறையுடன் தகவலை பகிர ஒப்புக்கொள்கிறீர்களா?\n\nதொடர *ஆம்* அல்லது ரத்து செய்ய *இல்லை* என்று எழுதுங்கள்.",
        "kn": "ಪ್ರಾರಂಭಿಸುವ ಮೊದಲು, Revenue ಇಲಾಖೆಯೊಂದಿಗೆ ಮಾಹಿತಿ ಹಂಚಿಕೊಳ್ಳಲು ನೀವು ಒಪ್ಪಿಗೆ ನೀಡುತ್ತೀರಾ?\n\nಮುಂದುವರಿಯಲು *ಹೌದು* ಅಥವಾ ರದ್ದು ಮಾಡಲು *ಇಲ್ಲ* ಎಂದು ಬರೆಯಿರಿ.",
        "ml": "ആരംഭിക്കുന്നതിന് മുൻപ്, Revenue വകുപ്പുമായി വിവരങ്ങൾ പങ്കിടാൻ നിങ്ങൾ സമ്മതിക്കുന്നുണ്ടോ?\n\nതുടരാൻ *അതെ* അല്ലെങ്കിൽ റദ്ദാക്കാൻ *ഇല്ല* എന്ന് എഴുതുക.",
        "bn": "শুরু করার আগে, আপনি কি Revenue বিভাগের সাথে তথ্য ভাগ করতে সম্মত?\n\nচালিয়ে যেতে *হ্যাঁ* বা বাতিল করতে *না* লিখুন।",
        "pa": "ਸ਼ੁਰੂ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ, ਕੀ ਤੁਸੀਂ Revenue ਵਿਭਾਗ ਨਾਲ ਜਾਣਕਾਰੀ ਸਾਂਝੀ ਕਰਨ ਲਈ ਸਹਿਮਤ ਹੋ?\n\nਜਾਰੀ ਰੱਖਣ ਲਈ *ਹਾਂ* ਜਾਂ ਰੱਦ ਕਰਨ ਲਈ *ਨਹੀਂ* ਲਿਖੋ।",
        "ur": "شروع کرنے سے پہلے، کیا آپ Revenue محکمے کے ساتھ معلومات شیئر کرنے پر رضامند ہیں؟\n\nجاری رکھنے کے لیے *ہاں* یا منسوخ کرنے کے لیے *نہیں* لکھیں۔",
        "or": "ଆରମ୍ଭ କରିବା ପୂର୍ବରୁ, ଆପଣ Revenue ବିଭାଗ ସହ ତଥ୍ୟ ଅଂଶୀଦାର କରିବାକୁ ସମ୍ମତ?\n\nଜାରି ରଖିବା ପାଇଁ *ହଁ* ବା ବାତିଲ ପାଇଁ *ନା* ଲେଖନ୍ତୁ।",
        "as": "আৰম্ভ কৰাৰ আগতে, আপুনি Revenue বিভাগৰ সৈতে তথ্য ভাগ কৰিবলৈ সম্মত নে?\n\nঅব্যাহত ৰাখিবলৈ *হয়* বা বাতিল কৰিবলৈ *নহয়* লিখক।",
    },

    # ── Service Selection Menu ──────────────────────────────────────────────
    "service_menu": {
        "en": "Please choose a service:\n\n1️⃣ Income Certificate\n2️⃣ Caste Certificate\n3️⃣ OBC-NCL Certificate\n4️⃣ Domicile Certificate\n\nReply with the number or name of the service.",
        "hi": "कृपया एक सेवा चुनें:\n\n1️⃣ आय प्रमाण पत्र\n2️⃣ जाति प्रमाण पत्र\n3️⃣ OBC-NCL प्रमाण पत्र\n4️⃣ निवास प्रमाण पत्र\n\nसेवा का नाम या नंबर लिखें।",
        "mr": "कृपया सेवा निवडा:\n\n1️⃣ उत्पन्न प्रमाणपत्र\n2️⃣ जात प्रमाणपत्र\n3️⃣ OBC-NCL प्रमाणपत्र\n4️⃣ अधिवास प्रमाणपत्र\n\nसेवेचे नाव किंवा क्रमांक लिहा.",
        "gu": "કૃપા કરી સેવા પસંદ કરો:\n\n1️⃣ આવક પ્રમાણ-પત્ર\n2️⃣ જ્ઞાતિ પ્રમાણ-પત્ર\n3️⃣ OBC-NCL પ્રમાણ-પત્ર\n4️⃣ નિવાસ પ્રમાણ-પત્ર",
        "te": "దయచేసి సేవను ఎంచుకోండి:\n\n1️⃣ ఆదాయ ధృవీకరణ పత్రం\n2️⃣ కులం ధృవీకరణ పత్రం\n3️⃣ OBC-NCL ధృవీకరణ పత్రం\n4️⃣ నివాస ధృవీకరణ పత్రం",
        "ta": "சேவையை தேர்வு செய்யவும்:\n\n1️⃣ வருமான சான்றிதழ்\n2️⃣ சாதி சான்றிதழ்\n3️⃣ OBC-NCL சான்றிதழ்\n4️⃣ வதிவிட சான்றிதழ்",
        "kn": "ದಯವಿಟ್ಟು ಸೇವೆಯನ್ನು ಆಯ್ಕೆ ಮಾಡಿ:\n\n1️⃣ ಆದಾಯ ಪ್ರಮಾಣಪತ್ರ\n2️⃣ ಜಾತಿ ಪ್ರಮಾಣಪತ್ರ\n3️⃣ OBC-NCL ಪ್ರಮಾಣಪತ್ರ\n4️⃣ ನಿವಾಸ ಪ್ರಮಾಣಪತ್ರ",
        "ml": "ദയവായി സേവനം തിരഞ്ഞെടുക്കുക:\n\n1️⃣ വരുമാന സർട്ടിഫിക്കറ്റ്\n2️⃣ ജാതി സർട്ടിഫിക്കറ്റ്\n3️⃣ OBC-NCL സർട്ടിഫിക്കറ്റ്\n4️⃣ ആധിവാസ സർട്ടിഫിക്കറ്റ്",
        "bn": "অনুগ্রহ করে একটি সেবা বেছে নিন:\n\n1️⃣ আয় সনদপত্র\n2️⃣ জাতি সনদপত্র\n3️⃣ OBC-NCL সনদপত্র\n4️⃣ বাসস্থান সনদপত্র",
        "pa": "ਕਿਰਪਾ ਕਰਕੇ ਸੇਵਾ ਚੁਣੋ:\n\n1️⃣ ਆਮਦਨ ਸਰਟੀਫਿਕੇਟ\n2️⃣ ਜਾਤੀ ਸਰਟੀਫਿਕੇਟ\n3️⃣ OBC-NCL ਸਰਟੀਫਿਕੇਟ\n4️⃣ ਰਿਹਾਇਸ਼ੀ ਸਰਟੀਫਿਕੇਟ",
        "ur": "براہ کرم سروس منتخب کریں:\n\n1️⃣ آمدنی سرٹیفکیٹ\n2️⃣ ذات سرٹیفکیٹ\n3️⃣ OBC-NCL سرٹیفکیٹ\n4️⃣ رہائش سرٹیفکیٹ",
        "or": "ଦୟାକରି ସେବା ବାଛନ୍ତୁ:\n\n1️⃣ ଆୟ ପ୍ରମାଣ ପତ୍ର\n2️⃣ ଜାତି ପ୍ରମାଣ ପତ୍ର\n3️⃣ OBC-NCL ପ୍ରମାଣ ପତ୍ର\n4️⃣ ବାସସ୍ଥାନ ପ୍ରମାଣ ପତ୍ର",
        "as": "অনুগ্ৰহ কৰি সেৱা বাছক:\n\n1️⃣ আয় প্ৰমাণপত্ৰ\n2️⃣ জাতি প্ৰমাণপত্ৰ\n3️⃣ OBC-NCL প্ৰমাণপত্ৰ\n4️⃣ বাসস্থান প্ৰমাণপত্ৰ",
    },

    # ── Payment Request ────────────────────────────────────────────────────
    "payment_request": {
        "en": "💳 Please pay the application fee of ₹{amount}.\n\nUPI: {upi_vpa}\nQR: {qr_link}\n\nAfter payment, send a screenshot or receipt here.",
        "hi": "💳 कृपया ₹{amount} का आवेदन शुल्क जमा करें।\n\nUPI: {upi_vpa}\nQR: {qr_link}\n\nभुगतान के बाद स्क्रीनशॉट यहाँ भेजें।",
        "mr": "💳 कृपया ₹{amount} अर्ज शुल्क भरा.\n\nUPI: {upi_vpa}\nQR: {qr_link}\n\nपेमेंट केल्यावर स्क्रीनशॉट इथे पाठवा.",
        "gu": "💳 ₹{amount} ફી ભરો. UPI: {upi_vpa}. ચૂકવ્યા પછી સ્ક્રીનશૉટ મોકલો.",
        "te": "💳 ₹{amount} ఫీజు చెల్లించండి. UPI: {upi_vpa}. చెల్లించిన తర్వాత స్క్రీన్‌షాట్ పంపండి.",
        "ta": "💳 ₹{amount} கட்டணம் செலுத்தவும். UPI: {upi_vpa}. செலுத்திய பிறகு ஸ்கிரீன்ஷாட் அனுப்பவும்.",
        "kn": "💳 ₹{amount} ಶುಲ್ಕ ಪಾವತಿ ಮಾಡಿ. UPI: {upi_vpa}. ಪಾವತಿ ನಂತರ ಸ್ಕ್ರೀನ್‌ಶಾಟ್ ಕಳುಹಿಸಿ.",
        "ml": "💳 ₹{amount} ഫീ അടക്കുക. UPI: {upi_vpa}. അടച്ചതിനുശേഷം സ്ക്രീൻഷോട്ട് അയക്കുക.",
        "bn": "💳 ₹{amount} ফি দিন। UPI: {upi_vpa}। পেমেন্টের পরে স্ক্রিনশট পাঠান।",
        "pa": "💳 ₹{amount} ਫ਼ੀਸ ਅਦਾ ਕਰੋ। UPI: {upi_vpa}। ਭੁਗਤਾਨ ਤੋਂ ਬਾਅਦ ਸਕ੍ਰੀਨਸ਼ੌਟ ਭੇਜੋ।",
        "ur": "💳 ₹{amount} فیس ادا کریں۔ UPI: {upi_vpa}۔ ادائیگی کے بعد اسکرین شاٹ بھیجیں۔",
        "or": "💳 ₹{amount} ଶୁଳ୍କ ପ୍ରଦାନ କରନ୍ତୁ। UPI: {upi_vpa}। ଦେବା ପରେ ସ୍କ୍ରିନଶଟ ପଠାନ୍ତୁ।",
        "as": "💳 ₹{amount} মাচুল পৰিশোধ কৰক। UPI: {upi_vpa}। পেমেন্টৰ পিছত স্ক্ৰীনশ্বট পাঠাওক।",
    },

    # ── Submission Confirmation ────────────────────────────────────────────
    "submission_success": {
        "en": "✅ Your application has been submitted successfully!\n\n📋 Tracking ID: *{tracking_id}*\n🕒 Processing time: 7 working days\n\nUse this ID to check status anytime via:\n• This chat\n• Web: revenuegov.in/track/{tracking_id}",
        "hi": "✅ आपका आवेदन सफलतापूर्वक जमा हो गया!\n\n📋 ट्रैकिंग आईडी: *{tracking_id}*\n🕒 प्रसंस्करण समय: 7 कार्य दिवस\n\nस्थिति जाँचने के लिए इस आईडी का उपयोग करें।",
        "mr": "✅ तुमचा अर्ज यशस्वीरित्या सादर झाला!\n\n📋 ट्रॅकिंग आयडी: *{tracking_id}*\n🕒 प्रक्रिया वेळ: 7 कामकाजाचे दिवस",
        "gu": "✅ અરજી સફળતાપૂર્વક સબમિટ!\n📋 ટ્રૅકિંગ ID: *{tracking_id}*\n🕒 7 કામકાજના દિવસ",
        "te": "✅ దరఖాస్తు విజయవంతంగా సమర్పించబడింది!\n📋 ట్రాకింగ్ ID: *{tracking_id}*\n🕒 7 పని దినాలు",
        "ta": "✅ விண்ணப்பம் வெற்றிகரமாக சமர்ப்பிக்கப்பட்டது!\n📋 ட்ராக்கிங் ID: *{tracking_id}*\n🕒 7 வேலை நாட்கள்",
        "kn": "✅ ಅರ್ಜಿ ಯಶಸ್ವಿಯಾಗಿ ಸಲ್ಲಿಸಲಾಗಿದೆ!\n📋 ಟ್ರ್ಯಾಕಿಂಗ್ ID: *{tracking_id}*\n🕒 7 ಕೆಲಸದ ದಿನಗಳು",
        "ml": "✅ അപേക്ഷ വിജയകരമായി സമർപ്പിച്ചു!\n📋 ട്രാക്കിംഗ് ID: *{tracking_id}*\n🕒 7 പ്രവൃത്തി ദിവസങ്ങൾ",
        "bn": "✅ আবেদন সফলভাবে জমা দেওয়া হয়েছে!\n📋 ট্র্যাকিং ID: *{tracking_id}*\n🕒 7 কার্যদিবস",
        "pa": "✅ ਅਰਜ਼ੀ ਸਫਲਤਾਪੂਰਵਕ ਜਮ੍ਹਾਂ!\n📋 ਟ੍ਰੈਕਿੰਗ ID: *{tracking_id}*\n🕒 7 ਕੰਮਕਾਜੀ ਦਿਨ",
        "ur": "✅ درخواست کامیابی سے جمع!\n📋 ٹریکنگ ID: *{tracking_id}*\n🕒 7 کام کے دن",
        "or": "✅ ଆବେଦନ ସଫଳଭାବେ ଦାଖଲ!\n📋 ଟ୍ରାକିଂ ID: *{tracking_id}*\n🕒 7 କାର୍ଯ୍ୟ ଦିନ",
        "as": "✅ আবেদন সফলভাৱে দাখিল!\n📋 ট্ৰেকিং ID: *{tracking_id}*\n🕒 7 কাৰ্যদিন",
    },

    # ── Status Update Notification ─────────────────────────────────────────
    "status_update": {
        "en": "📱 Update for your application *{tracking_id}*:\n\nStatus: *{status}*\n{details}\n\nReply STATUS to check again.",
        "hi": "📱 आपके आवेदन *{tracking_id}* का अपडेट:\n\nस्थिति: *{status}*\n{details}\n\nदोबारा जाँचने के लिए STATUS लिखें।",
        "mr": "📱 तुमच्या अर्ज *{tracking_id}* चे अपडेट:\n\nस्थिती: *{status}*\n{details}",
        "gu": "📱 *{tracking_id}* અપડેટ:\nસ્થિતિ: *{status}*",
        "te": "📱 *{tracking_id}* నవీకరణ:\nస్థితి: *{status}*",
        "ta": "📱 *{tracking_id}* புதுப்பிப்பு:\nநிலை: *{status}*",
        "kn": "📱 *{tracking_id}* ನವೀಕರಣ:\nಸ್ಥಿತಿ: *{status}*",
        "ml": "📱 *{tracking_id}* അപ്ഡേറ്റ്:\nനില: *{status}*",
        "bn": "📱 *{tracking_id}* আপডেট:\nঅবস্থা: *{status}*",
        "pa": "📱 *{tracking_id}* ਅੱਪਡੇਟ:\nਸਥਿਤੀ: *{status}*",
        "ur": "📱 *{tracking_id}* اپڈیٹ:\nحالت: *{status}*",
        "or": "📱 *{tracking_id}* ଅପଡ଼େଟ:\nସ୍ଥିତି: *{status}*",
        "as": "📱 *{tracking_id}* আপডেট:\nস্থিতি: *{status}*",
    },

    # ── Error / Fallback ───────────────────────────────────────────────────
    "error_fallback": {
        "en": "Sorry, I didn't understand that. Could you please repeat? Or type *HELP* for options.",
        "hi": "क्षमा करें, मैं समझ नहीं पाया। कृपया दोहराएं? या विकल्पों के लिए *HELP* लिखें।",
        "mr": "माफ करा, मला समजले नाही. पुन्हा सांगाल का? किंवा *HELP* लिहा.",
        "gu": "માફ કરો, સમજાયું નહીં. ફરી કહો? *HELP* ટાઇપ કરો.",
        "te": "క్షమించండి, అర్థం కాలేదు. మళ్ళీ చెప్పగలరా? *HELP* టైప్ చేయండి.",
        "ta": "மன்னிக்கவும், புரியவில்லை. மீண்டும் சொல்லுங்கள்? *HELP* என்று தட்டச்சு செய்யுங்கள்.",
        "kn": "ಕ್ಷಮಿಸಿ, ಅರ್ಥವಾಗಲಿಲ್ಲ. ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ? *HELP* ಟೈಪ್ ಮಾಡಿ.",
        "ml": "ക്ഷമിക്കൂ, മനസ്സിലായില്ല. വീണ്ടും പറയൂ? *HELP* ടൈപ്പ് ചെയ്യൂ.",
        "bn": "দুঃখিত, বুঝতে পারিনি। আবার বলুন? *HELP* টাইপ করুন।",
        "pa": "ਮਾਫ਼ ਕਰਨਾ, ਸਮਝ ਨਹੀਂ ਆਇਆ। ਦੁਬਾਰਾ ਦੱਸੋ? *HELP* ਲਿਖੋ।",
        "ur": "معاف کریں، سمجھ نہیں آیا۔ دوبارہ بتائیں؟ *HELP* ٹائپ کریں۔",
        "or": "ଦୁଃଖিତ, ବୁଝି ପାରିଲି ନାହିଁ। ଦୟାକରି ପୁନଃ ଦୋହୋ? *HELP* ଟାଇପ କରନ୍ତୁ।",
        "as": "দুঃখিত, বুজা নগল। আকৌ কওক? *HELP* টাইপ কৰক।",
    },
}


# ── IVR Voice Prompts ──────────────────────────────────────────────────────

IVR_PROMPTS: Dict[str, Dict[str, str]] = {
    "welcome": {
        "en": "Welcome to RevenueSeva. Press 1 to check application status. Press 2 to get tracking ID. Press 3 for payment information. Press 0 to repeat.",
        "hi": "RevenueSeva में आपका स्वागत है। आवेदन की स्थिति जानने के लिए 1 दबाएं। ट्रैकिंग आईडी के लिए 2 दबाएं। भुगतान जानकारी के लिए 3 दबाएं। दोहराने के लिए 0 दबाएं।",
        "mr": "RevenueSeva मध्ये स्वागत आहे. अर्जाची स्थिती जाणण्यासाठी 1 दाबा. ट्रॅकिंग आयडीसाठी 2 दाबा. पेमेंटसाठी 3 दाबा. पुन्हा ऐकण्यासाठी 0 दाबा.",
    },
    "status_result": {
        "en": "Your application {tracking_id} is currently {status}. Estimated completion in {days} working days.",
        "hi": "आपके आवेदन {tracking_id} की स्थिति {status} है। {days} कार्य दिवसों में पूरा होने की उम्मीद है।",
        "mr": "तुमचा अर्ज {tracking_id} सध्या {status} आहे. {days} कामकाजाच्या दिवसात पूर्ण होईल.",
    },
    "not_found": {
        "en": "Sorry, we could not find an application with that ID. Please check and try again.",
        "hi": "क्षमा करें, उस आईडी से कोई आवेदन नहीं मिला। कृपया जाँच करें और पुनः प्रयास करें।",
        "mr": "माफ करा, त्या आयडीने कोणताही अर्ज सापडला नाही. कृपया तपासा आणि पुन्हा प्रयत्न करा.",
    },
    "goodbye": {
        "en": "Thank you for calling RevenueSeva. Goodbye!",
        "hi": "RevenueSeva को कॉल करने के लिए धन्यवाद। नमस्ते!",
        "mr": "RevenueSeva ला कॉल केल्याबद्दल धन्यवाद. नमस्कार!",
    },
}


# ── Template Helper ────────────────────────────────────────────────────────

def get_template(key: str, language: str = "en", **kwargs) -> str:
    """
    Get i18n template string for a key, formatted with kwargs.
    Falls back to English if language not available.
    """
    templates = TEMPLATES.get(key, {})
    text = templates.get(language, templates.get("en", key))
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def get_ivr_prompt(key: str, language: str = "en", **kwargs) -> str:
    """Get IVR voice prompt for a key."""
    prompts = IVR_PROMPTS.get(key, {})
    text = prompts.get(language, prompts.get("en", key))
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def get_status_message(status: str, language: str = "en", **kwargs) -> str:
    """Get a citizen-facing message for an application status."""
    from app.orchestration.state_machine.application_fsm import CITIZEN_MESSAGES
    messages = CITIZEN_MESSAGES.get(status, {})
    text = messages.get(language, messages.get("en", status))
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text
