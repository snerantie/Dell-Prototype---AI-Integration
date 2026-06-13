"""Localised static UI strings for the menu/navigation layer.

These are the fixed strings learners see most (menus, prompts, system
messages). Keeping them in a table means the WhatsApp greeting and the entire
USSD flow are multilingual even in fully offline mock mode — dynamic tutoring
text is handled separately by the TranslationProvider.

NOTE: the isiZulu (zu) and isiXhosa (xh) strings below are first-pass and should
be validated by native-speaking educators before any public pilot.
"""
from __future__ import annotations

# key -> { lang_code -> string }.  English ("en") is the guaranteed fallback.
_STRINGS: dict[str, dict[str, str]] = {
    "welcome": {
        "en": "Welcome to AI Tutor",
        "af": "Welkom by AI Tutor",
        "zu": "Sawubona, wamukelekile ku-AI Tutor",
        "xh": "Wamkelekile kwi-AI Tutor",
    },
    "whatsapp_intro": {
        "en": "Hi! I'm your AI Maths tutor. Send me a problem (e.g. 2x+3=7) or a "
              "photo of your working, and I'll help you find where you're stuck.",
        "af": "Hallo! Ek is jou AI Wiskunde-tutor. Stuur 'n som (bv. 2x+3=7) of 'n "
              "foto van jou bewerking, en ek sal help om te sien waar jy vassit.",
        "zu": "Sawubona! Ngingumeluleki wakho we-Izibalo we-AI. Thumela inkinga "
              "(isb. 2x+3=7) noma isithombe somsebenzi wakho, ngizokusiza ubone "
              "lapho unqindeka khona.",
        "xh": "Molo! Ndingumcebisi wakho we-Izibalo we-AI. Thumela ingxaki "
              "(umz. 2x+3=7) okanye ifoto yomsebenzi wakho, ndizokunceda ubone "
              "apho uxakeka khona.",
    },
    "choose_language": {
        "en": "Choose your language:",
        "af": "Kies jou taal:",
        "zu": "Khetha ulimi lwakho:",
        "xh": "Khetha ulwimi lwakho:",
    },
    "choose_subject": {
        "en": "Choose a subject:",
        "af": "Kies 'n vak:",
        "zu": "Khetha isifundo:",
        "xh": "Khetha isifundo:",
    },
    "subject_mathematics": {
        "en": "Mathematics", "af": "Wiskunde", "zu": "Izibalo", "xh": "Izibalo",
    },
    "ask_problem": {
        "en": "Type the equation you're stuck on (e.g. 2x+3=7):",
        "af": "Tik die vergelyking waarmee jy vassit (bv. 2x+3=7):",
        "zu": "Bhala isibalo onqindeka kuso (isb. 2x+3=7):",
        "xh": "Bhala isibalo oxakeka kuso (umz. 2x+3=7):",
    },
    "ask_working": {
        "en": "Now type your working — one step per line. Reply with your steps.",
        "af": "Tik nou jou bewerking — een stap per reël. Antwoord met jou stappe.",
        "zu": "Manje bhala indlela oyenzile — isinyathelo ngasinye emugqeni.",
        "xh": "Ngoku bhala indlela oyenzileyo — inyathelo ngalinye kumgca.",
    },
    "analyzing": {
        "en": "Let me look at your thinking...",
        "af": "Laat ek na jou denke kyk...",
        "zu": "Ake ngibheke indlela ocabanga ngayo...",
        "xh": "Mandijonge indlela ocinga ngayo...",
    },
    "invalid_option": {
        "en": "Sorry, that option isn't valid. Please try again.",
        "af": "Jammer, daardie opsie is ongeldig. Probeer asseblief weer.",
        "zu": "Uxolo, lelo khetho alilungile. Sicela uzame futhi.",
        "xh": "Uxolo, olo khetho alusebenzi. Nceda uzame kwakhona.",
    },
    "goodbye": {
        "en": "Keep practising! Dial again any time.",
        "af": "Bly oefen! Skakel weer enige tyd.",
        "zu": "Qhubeka uzilolonge! Shayela futhi noma nini.",
        "xh": "Qhubeka uziqhelanise! Tsalela kwakhona nanini na.",
    },
    "no_equation": {
        "en": "I couldn't spot an equation there.",
        "af": "Ek kon nie 'n vergelyking daar opspoor nie.",
        "zu": "Angikwazanga ukubona isibalo lapho.",
        "xh": "Andikwazanga ukubona isibalo apho.",
    },
    "lets_work": {
        "en": "Great, let's work on this together.",
        "af": "Wonderlik, kom ons werk hieraan saam.",
        "zu": "Kuhle, ake sisebenze ndawonye kulokhu.",
        "xh": "Kuhle, masenze lo msebenzi kunye.",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Translate a UI key into ``lang``, falling back to English then the key."""
    entry = _STRINGS.get(key, {})
    return entry.get(lang) or entry.get("en") or key
