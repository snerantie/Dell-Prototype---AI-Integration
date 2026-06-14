"""Localised user-facing strings for the AI Tutor.

The whole user-facing surface (menus, greetings, Socratic prompts, misconception
hints, diagnosis summaries) lives here so the offline mock demo is fully
multilingual without needing a translation model. Dynamic content the LLM
generates in real Dell mode is still routed through the TranslationProvider.

NOTE: First-pass Nguni (zu/xh) translations should be reviewed by native-
speaking educators before any public pilot. They are sufficient for prototype
demos.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import MisconceptionType

# ----------------------------------------------------------------------------
# Static UI strings (menus, prompts, system messages)
# ----------------------------------------------------------------------------
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

    # ----- Pedagogy framing (parametric — use tf() with .format kwargs) -----
    "ped_intro_step": {
        "en": "Good effort — your approach is on the right path. Let's look at "
              "your {ordinal} step together.",
        "af": "Goeie poging — jou benadering is op die regte spoor. Kom ons kyk "
              "saam na jou {ordinal} stap.",
        "zu": "Umzamo omuhle — indlela yakho ilungile. Ake sihlole isinyathelo "
              "{ordinal} sakho ndawonye.",
        "xh": "Umzamo omhle — indlela yakho ichanile. Masijonge inyathelo "
              "{ordinal} lakho kunye.",
    },
    "ped_try_again": {
        "en": "Try re-doing just that line, then send me your new version. "
              "Reply *HINT* if you'd like another clue, or *STEP* to work "
              "through it one line at a time.",
        "af": "Probeer net daardie reël oor te doen, en stuur dan jou nuwe "
              "weergawe. Antwoord *HINT* vir nog 'n leidraad, of *STEP* om "
              "stap-vir-stap te werk.",
        "zu": "Zama ukubuyekeza lowo mugqa kuphela, bese ungithumela inguqulo "
              "entsha. Phendula *HINT* uma ufuna olunye usizo, noma *STEP* "
              "ukusebenza ngenyathelo ngalinye.",
        "xh": "Zama ukuphinda wenze loo mgca kuphela, uze undithumele inguqulelo "
              "entsha. Phendula *HINT* ukuba ufuna omnye umkhondo, okanye "
              "*STEP* ukusebenza ngenyathelo ngalinye.",
    },
    "ped_correct_affirm": {
        "en": "Nicely done — your working is correct. ✅",
        "af": "Mooi gedoen — jou bewerking is reg. ✅",
        "zu": "Wenze kahle — umsebenzi wakho ulungile. ✅",
        "xh": "Wenze kakuhle — umsebenzi wakho uchanile. ✅",
    },
    "ped_correct_check": {
        "en": "Quick check that you *understand* it: which operation did you "
              "use to get x on its own, and why does it keep the equation "
              "balanced?",
        "af": "Vinnige toets dat jy dit *verstaan*: watter bewerking het jy "
              "gebruik om x op sy eie te kry, en hoekom hou dit die vergelyking "
              "gebalanseerd?",
        "zu": "Hlola ngokushesha ukuthi *uyakuqonda yini*: yiluphi usebenzo "
              "olusebenzisile ukuze u-x ime yodwa, futhi kungani kugcina "
              "isibalo silingana?",
        "xh": "Vavanya ngokukhawuleza ukuba *uyayiqonda na*: nguwuphi umsebenzi "
              "owusebenzisileyo ukuze u-x ime yodwa, kwaye kutheni kugcina "
              "umzekeliso ulingana?",
    },
    "ped_want_thinking": {
        "en": "I want to understand how you're thinking about this.",
        "af": "Ek wil verstaan hoe jy hieroor dink.",
        "zu": "Ngifuna ukuqonda ukuthi ucabanga kanjani ngalokhu.",
        "xh": "Ndifuna ukuqonda indlela ocinga ngayo.",
    },
    "ped_send_photo": {
        "en": "Could you send a photo of your working, or type each line of "
              "your steps? Then I can show you exactly where to look.",
        "af": "Kan jy 'n foto van jou bewerking stuur, of elke reël van jou "
              "stappe tik? Dan kan ek jou wys waar om te kyk.",
        "zu": "Ungangithumela isithombe somsebenzi wakho, noma ubhale umugqa "
              "ngamunye wezinyathelo zakho? Bese ngingakukhombisa ukuthi "
              "ubhekephi.",
        "xh": "Ungandithumela ifoto yomsebenzi wakho, okanye ubhale umgca "
              "ngamnye wamanyathelo akho? Ndingakubonisa apho ukujonge khona.",
    },
    "ped_look_at_step": {
        "en": "Look closely at step {n}: \"{line}\".",
        "af": "Kyk noukeurig na stap {n}: \"{line}\".",
        "zu": "Bheka ngokucophelela isinyathelo {n}: \"{line}\".",
        "xh": "Jonga ngenyameko inyathelo {n}: \"{line}\".",
    },
    "ped_breaks_balance": {
        "en": "Something on this line breaks the balance of the equation.",
        "af": "Iets op hierdie reël breek die balans van die vergelyking.",
        "zu": "Okuthile kulo mugqa kwephula ukulingana kwesibalo.",
        "xh": "Kukho into kulo mgca eyaphula ukulingana komzekeliso.",
    },
    "ped_what_should": {
        "en": "What should that line be instead? Send me your corrected version.",
        "af": "Wat moet daardie reël eerder wees? Stuur jou regstelling.",
        "zu": "Lowo mugqa kufanele ube yini esikhundleni salokho? Ngithumele "
              "inguqulo elungisiwe.",
        "xh": "Loo mgca ufanele ube yintoni endaweni yoko? Ndithumele "
              "inguqulelo elungisiweyo.",
    },
    "ped_work_together": {
        "en": "Let's work step {n} together: \"{line}\".",
        "af": "Kom ons werk stap {n} saam deur: \"{line}\".",
        "zu": "Ake sisebenze isinyathelo {n} ndawonye: \"{line}\".",
        "xh": "Masisebenzise inyathelo {n} kunye: \"{line}\".",
    },
    "ped_apply_finish": {
        "en": "Apply that idea to this line, redo just this step, and tell me "
              "your new line — I'll check it. (I won't give the final answer; "
              "you're nearly there!)",
        "af": "Pas daardie idee op hierdie reël toe, doen net hierdie stap "
              "oor, en gee my jou nuwe reël — ek sal dit nagaan. (Ek sal nie "
              "die finale antwoord gee nie; jy's amper daar!)",
        "zu": "Sebenzisa lowo mqondo kulo mugqa, yenza kabusha lesi sinyathelo "
              "kuphela, ungitshele umugqa wakho omusha — ngizowuhlola. "
              "(Angeke nginikeze impendulo yokugcina; ususeduze!)",
        "xh": "Sebenzisa loo mbono kulo mgca, phinda wenze elinyathelo kuphela, "
              "undixelele umgca wakho omtsha — ndizoyihlola. (Andisokuze "
              "ndinike impendulo yokugqibela; usele kufuphi!)",
    },

    # ----- Diagnosis summary (shown under bot replies) -----
    "sum_correct": {
        "en": "Working is correct. x = {value}.",
        "af": "Bewerking is reg. x = {value}.",
        "zu": "Umsebenzi ulungile. x = {value}.",
        "xh": "Umsebenzi uchanile. x = {value}.",
    },
    "sum_first_error": {
        "en": "First error at step {n}. Correct solution is x = {value}.",
        "af": "Eerste fout by stap {n}. Korrekte oplossing is x = {value}.",
        "zu": "Iphutha lokuqala esinyathelweni {n}. Isisombululo esilungile "
              "sithi x = {value}.",
        "xh": "Impazamo yokuqala kunyathelo {n}. Isisombululo esichanileyo "
              "sithi x = {value}.",
    },
    "sum_only_solution": {
        "en": "Correct solution is x = {value}.",
        "af": "Korrekte oplossing is x = {value}.",
        "zu": "Isisombululo esilungile sithi x = {value}.",
        "xh": "Isisombululo esichanileyo sithi x = {value}.",
    },

    # ----- USSD nudges -----
    "ussd_check_step": {
        "en": "Check step {n}.",
        "af": "Kyk na stap {n}.",
        "zu": "Bheka isinyathelo {n}.",
        "xh": "Jonga inyathelo {n}.",
    },
    "ussd_corrected_line": {
        "en": "Type your corrected line:",
        "af": "Tik jou regstelling:",
        "zu": "Bhala umugqa wakho olungisiwe:",
        "xh": "Bhala umgca wakho olungisiweyo:",
    },
    "ussd_correct": {
        "en": "Correct! {answer}.",
        "af": "Reg! {answer}.",
        "zu": "Lungile! {answer}.",
        "xh": "Ichanile! {answer}.",
    },
    "ussd_continue": {
        "en": "Looks right so far. Enter your next step (or x = ... for your "
              "answer):",
        "af": "Lyk reg tot dusver. Voer jou volgende stap in (of x = ... vir "
              "jou antwoord):",
        "zu": "Kubukeka kulungile kuze kube manje. Faka isinyathelo sakho "
              "esilandelayo (noma x = ... ngempendulo yakho):",
        "xh": "Kubonakala kuchanile okwangoku. Faka inyathelo lakho "
              "elilandelayo (okanye x = ... ngempendulo yakho):",
    },

    # ----- Ordinals (used inside ped_intro_step) -----
    "ord_1": {"en": "first",  "af": "eerste",  "zu": "sokuqala",   "xh": "lokuqala"},
    "ord_2": {"en": "second", "af": "tweede",  "zu": "sesibili",   "xh": "lesibini"},
    "ord_3": {"en": "third",  "af": "derde",   "zu": "sesithathu", "xh": "lesithathu"},
    "ord_4": {"en": "fourth", "af": "vierde",  "zu": "sesine",     "xh": "lesine"},
    "ord_5": {"en": "fifth",  "af": "vyfde",   "zu": "sesihlanu",  "xh": "lesihlanu"},
}


# ----------------------------------------------------------------------------
# Localised misconception hints (educational content)
# ----------------------------------------------------------------------------
MISCONCEPTION_HINTS_I18N: dict[MisconceptionType, dict[str, str]] = {
    MisconceptionType.SIGN_ERROR: {
        "en": "Check your signs. When you multiply or divide by a negative, "
              "every sign changes. Which sign looks off on that line?",
        "af": "Kyk na jou tekens. Wanneer jy met 'n negatief vermenigvuldig of "
              "deel, verander elke teken. Watter teken lyk verkeerd op "
              "daardie reël?",
        "zu": "Bheka izimpawu zakho. Uma uphindaphinda noma uhlukanisa "
              "ngenani elingelimi, zonke izimpawu ziyashintsha. Yiluphi "
              "uphawu olungalungile kulo mugqa?",
        "xh": "Jonga iimpawu zakho. Xa uphinda-phinda okanye uhlula ngenani "
              "elingelilo, zonke iimpawu ziyatshintsha. Yiyiphi impawu "
              "engachananga kulo mgca?",
    },
    MisconceptionType.TRANSPOSITION: {
        "en": "When a term crosses the = sign, its sign must flip (+ becomes "
              "-, - becomes +). Re-do that move and see what changes.",
        "af": "Wanneer 'n term oor die =-teken beweeg, moet sy teken omslaan "
              "(+ word -, - word +). Doen daardie skuif oor en kyk wat "
              "verander.",
        "zu": "Uma ithemu iwela ngale kophawu lwe-=, uphawu lwayo kufanele "
              "luguquke (+ luba -, - luba +). Phinda lokho kunyakaza ubone "
              "ukuthi yini eshintshayo.",
        "xh": "Xa igama liwela kwicala lelinye lophawu lwe-=, uphawu lwalo "
              "kufanele luguquke (+ luba -, - luba +). Phinda olo nyakazo "
              "ubone ukuba kutshintsha ntoni.",
    },
    MisconceptionType.DISTRIBUTION: {
        "en": "When you remove a bracket, every term inside must be "
              "multiplied. Did each term get multiplied?",
        "af": "Wanneer jy 'n hakie verwyder, moet elke term binne "
              "vermenigvuldig word. Het elke term vermenigvuldig geword?",
        "zu": "Uma ususa abakaki, yonke ithemu engaphakathi kufanele "
              "iphindaphindwe. Ngabe yonke ithemu iphindaphindwe?",
        "xh": "Xa ususa izibiyeli, igama ngalinye elingaphakathi kufuneka "
              "liphindaphindwe. Ngaba igama ngalinye liphindwe-phindwa?",
    },
    MisconceptionType.FACTORISATION: {
        "en": "Multiply your factors back out. Do you get the original "
              "expression?",
        "af": "Vermenigvuldig jou faktore weer uit. Kry jy die oorspronklike "
              "uitdrukking?",
        "zu": "Phindaphinda izici zakho ubuyele. Ngabe ufumana inkulumo "
              "yokuqala?",
        "xh": "Phindaphinda iziphumo zakho ubuyele emva. Ngaba uyalifumana "
              "ibinzana lokuqala?",
    },
    MisconceptionType.FRACTION_HANDLING: {
        "en": "When you divide, divide EVERY term on BOTH sides by the same "
              "number. Did each term get divided?",
        "af": "Wanneer jy deel, deel ELKE term aan ALBEI kante deur dieselfde "
              "getal. Het elke term gedeel geword?",
        "zu": "Uma uhlukanisa, hlukanisa YONKE ithemu KUZO ZOMBILI "
              "izinhlangothi ngenani elifanayo. Ngabe yonke ithemu "
              "yahlukaniswa?",
        "xh": "Xa uhlula, hlula IGAMA NGALINYE KWAMACALA OMABINI ngenani "
              "elifanayo. Ngaba igama ngalinye lihluliwe?",
    },
    MisconceptionType.SUBSTITUTION: {
        "en": "Re-check the value you put in. Did it go into every place the "
              "variable appears?",
        "af": "Kyk weer na die waarde wat jy ingesit het. Het dit in elke "
              "plek gegaan waar die veranderlike voorkom?",
        "zu": "Phinda uhlole inani olifakile. Ngabe lingene kuzo zonke "
              "izindawo lapho okuhlukile kuvela khona?",
        "xh": "Phinda ujonge ixabiso oligalileyo. Ngaba liye kuzo zonke "
              "iindawo apho uguquko luvela khona?",
    },
    MisconceptionType.ARITHMETIC_SLIP: {
        "en": "Your method is correct — there's just a small calculation slip "
              "on that line. Re-work that arithmetic slowly.",
        "af": "Jou metode is reg — daar is net 'n klein berekeningsfout op "
              "daardie reël. Werk daardie rekenkunde stadig oor.",
        "zu": "Indlela yakho ilungile — kunephutha elincane lokubala kuphela "
              "kulo mugqa. Phinda usebenze leyo arithmethi kancane.",
        "xh": "Indlela yakho ichanile — kukho impazamo encinci yokubala "
              "kuphela kulo mgca. Phinda usebenzise loo arithmethi "
              "ngokucothayo.",
    },
    MisconceptionType.CONCEPTUAL: {
        "en": "Let's pause on the idea behind this step. What are you trying "
              "to achieve on this line?",
        "af": "Kom ons stop by die idee agter hierdie stap. Wat probeer jy "
              "op hierdie reël bereik?",
        "zu": "Ake sime emqondweni ongemuva kwalesi sinyathelo. Yini ozama "
              "ukuyifeza kulo mugqa?",
        "xh": "Masimise umbono ongasemva kweli nyathelo. Yintoni ozama "
              "ukuyifezekisa kulo mgca?",
    },
    MisconceptionType.INCOMPLETE: {
        "en": "You're on the right track. What is the next step to get x on "
              "its own?",
        "af": "Jy is op die regte spoor. Wat is die volgende stap om x op "
              "sy eie te kry?",
        "zu": "Usendleleni elungile. Yisiphi isinyathelo esilandelayo "
              "sokuthola u-x ime yodwa?",
        "xh": "Usendleleni echanileyo. Yintoni inyathelo elilandelayo "
              "lokufumana u-x ime yodwa?",
    },
    MisconceptionType.NONE: {"en": "", "af": "", "zu": "", "xh": ""},
}


def t(key: str, lang: str = "en") -> str:
    """Translate a UI key into ``lang``, falling back to English then the key."""
    entry = _STRINGS.get(key, {})
    return entry.get(lang) or entry.get("en") or key


def tf(key: str, lang: str = "en", **params: Any) -> str:
    """Translate and format a parametric template (``{name}`` placeholders)."""
    template = t(key, lang)
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def ordinal(n: int, lang: str = "en") -> str:
    """Localised ordinal word for n in 1..5; falls back to ``Nth`` past 5."""
    return t(f"ord_{n}", lang) if 1 <= n <= 5 else f"{n}th"


def hint_for(misconception: MisconceptionType, lang: str = "en") -> str:
    """Localised Socratic hint for a misconception type."""
    entry = MISCONCEPTION_HINTS_I18N.get(misconception, {})
    return entry.get(lang) or entry.get("en") or ""
