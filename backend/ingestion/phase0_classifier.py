import sys
import json
import os
import re
import requests

# Fix Unicode output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ============================================
# CONFIGURATION
# ============================================
INPUT_FILE  = "backend/data/extracted/phase1_extracted.json"
OUTPUT_FILE = "backend/data/extracted/phase0_classified.json"
REPORT_FILE = "backend/data/classification_report.json"

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"

# Thresholds — raised to reduce false positives
KEYWORD_ACCEPT_THRESHOLD = 4   # was 3 — need stronger keyword signal
KEYWORD_REJECT_THRESHOLD = -1  # was -2 — reject earlier on negative signals
# Between 1–3 → send to LLM (much narrower band)
# Below -1 → auto reject
# Above 4 → auto accept

os.makedirs("backend/data/extracted", exist_ok=True)

# ============================================
# CORE TDR SIGNALS
# A genuine TdR MUST contain at least 2 of these.
# If it has < 2, it cannot be auto-accepted by keywords alone.
# ============================================
CORE_TDR_SIGNALS = [
    r"\bconsultant\b",
    r"\bconsultance\b",
    r"\brecrutement\b",
    r"\bappel\s+(d['\u2019]offre|[àa]\s+(candidature|consultation|consultants?))\b",
    r"\blivrables?\b",
    r"\bdeliverables?\b",
    r"\bscope\s+of\s+work\b",
    r"\bstatement\s+of\s+work\b",
    r"\btermes?\s+de\s+r[eé]f[eé]rence\b",
    r"\bterms?\s+of\s+reference\b",
    r"\bprofil\s+(recherch[eé]|du\s+consultant)\b",
    r"\bqualifications?\s+requises?\b",
    r"\bcompétences?\s+requises?\b",
    r"\bmandat\b",
    r"\bprestations?\s+(attendues?|requises?)\b",
    r"\bchef\s+de\s+mission\b",
    r"\bexpert\s+principal\b",
]

# ============================================
# POSITIVE KEYWORDS
# General TdR-related vocabulary (adds to score)
# ============================================
POSITIVE_KEYWORDS = [
    r"\bTd[Rr]\b",
    r"\bTDR\b",
    r"\btermes?\s+de\s+r[eé]f[eé]rence\b",
    r"\bterms?\s+of\s+reference\b",
    r"\bconsultant\b",
    r"\bconsultance\b",
    r"\bmission\b",
    r"\bmandat\b",
    r"\brecrutement\b",
    r"\bappel\s+(d['\u2019]offre|[àa]\s+candidature|[àa]\s+consultation|[àa]\s+consultants?)\b",
    r"\bprofil\s+(recherch[eé]|du\s+consultant)\b",
    r"\blivrables?\b",
    r"\bobjectifs?\s+de\s+la\s+mission\b",
    r"\bscope\s+of\s+work\b",
    r"\bstatement\s+of\s+work\b",
    r"\bqualifications?\s+requises?\b",
    r"\bcomp[eé]tences?\s+requises?\b",
    r"\bcrit[eè]res?\s+de\s+s[eé]lection\b",
    r"\bprestations?\b",
    r"\bexp[eé]rience\s+requise\b",
    r"\bd[eé]lai\s+d['\u2019]ex[eé]cution\b",
    r"\bchef\s+de\s+mission\b",
    r"\bexpert[·\s]+principal\b",
    r"\bbackground\s+and\s+justification\b",
    r"\bperiod\s+of\s+(performance|execution)\b",
    r"\bsolicitation\b",
]

# ============================================
# NEGATIVE KEYWORDS
# Strong signals the document is NOT a genuine TdR.
# Each match subtracts 2 from the score.
# ============================================
NEGATIVE_KEYWORDS = [
    # Reports and brochures
    r"\bprogress\s+report\b",
    r"\bannual\s+report\b",
    r"\brapport\s+(annuel|de\s+progr[eè]s|d['\u2019]avancement|final\b|de\s+constatations)\b",
    r"\bexpected\s+results?\b",
    r"\bat\s+a\s+glance\b",
    r"\bbrochure\b",
    r"\bflyer\b",
    r"\bnewsletter\b",

    # Presentations / slides
    r"\bslides?\b",
    r"\bseminar\b",
    r"\bconference\s+(paper|proceedings?)\b",
    r"\bpresented\s+(at|by)\b",
    r"\bpanelists?\b",
    r"\bpresentation\b",

    # Manuals and catalogues
    r"\buser\s+manual\b",
    r"\bmanuel\s+(d['\u2019]utilisation|utilisateur)\b",
    r"\bcatalogue\b",
    r"\bvehicle\s+manual\b",
    r"\binstallation\s+(manual|memo|guide|note)\b",

    # Technical / engineering (non-consultancy)
    r"\bgeophone\b",
    r"\brectangular\s+bends?\b",
    r"\bhydrodynamic\b",
    r"\bhigh.performance\s+computing\b",
    r"\bxfel\b",
    r"\bnetwork\s+of\s+fair\b",
    r"\btechnical\s+design\s+report\b",
    r"\bdesign\s+changes?\b",
    r"\bplan\s+de\s+montage\b",
    r"\bschéma\s+de\s+(montage|câblage)\b",
    r"\bdata\s+sheet\b",
    r"\bspecification\s+sheet\b",

    # Financial / legal (non-consultancy)
    r"\bmerger\b",
    r"\bacquisition\b",
    r"\bshareholder\b",
    r"\bhedge\s+fund\b",
    r"\binvestment\s+(fund|manager|vehicle)\b",
    r"\btax\s+jurisdiction\b",
    r"\bfinancial\s+statements?\b",
    r"\bearnings\s+per\s+share\b",
    r"\besg\s+(policy|principles|framework)\b",

    # Strategy / policy documents (not TdR)
    r"\bstrategy\s+\d{4}[-–]\d{4}\b",
    r"\bstrategic\s+plan\b",
    r"\bprocurement\s+regulations?\b",
    r"\bprocurement\s+(framework|guidelines?|rules?)\b",
    r"\bworld\s+bank\s+procurement\b",

    # Environmental / scientific reports
    r"\bPGES\b",
    r"\bplan\s+de\s+gestion\s+environnemental\b",
    r"\benvironmental\s+(management|impact)\s+(plan|assessment)\b",
    r"\bacademic\s+(article|paper|journal)\b",
    r"\babstract\b",
    r"\bkeywords?\s*:\s*\w+",  # academic paper structure
    r"\bintroduction\n.*\nmethods?\n",  # typical research paper structure
]


def count_core_signals(text: str) -> int:
    """Count how many core TdR signals appear in the text."""
    text_lower = text.lower()
    count = 0
    for pattern in CORE_TDR_SIGNALS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            count += 1
    return count


def score_document(text: str) -> tuple[int, list[str], list[str], int]:
    """
    Score a document based on keyword matching.
    Returns (score, matched_positive, matched_negative, core_signal_count).
    """
    text_lower = text.lower()
    matched_pos = []
    matched_neg = []

    for pattern in POSITIVE_KEYWORDS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            matched_pos.append(pattern)

    for pattern in NEGATIVE_KEYWORDS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            matched_neg.append(pattern)

    score = len(matched_pos) - (len(matched_neg) * 2)
    core_count = count_core_signals(text)
    return score, matched_pos, matched_neg, core_count


def ask_ollama(filename: str, text_snippet: str) -> tuple[bool, str]:
    """
    Ask Ollama LLM whether the document is a genuine TdR.
    Uses a much stricter prompt that explicitly lists what NOT to accept.
    Returns (is_tdr, reasoning).
    """
    snippet = text_snippet[:2000].strip()

    prompt = f"""You are a STRICT document classifier. Your ONLY job is to determine if a document is a genuine "Termes de Référence" (TdR / Terms of Reference / ToR).

A GENUINE TdR is a document that:
- Recruits or mandates a CONSULTANT or EXPERT for a specific MISSION
- Defines DELIVERABLES the consultant must produce
- Describes REQUIRED QUALIFICATIONS / PROFILE of the consultant
- Has a clear DURATION / TIMELINE for the mission
- Is written by an organization HIRING someone for a service

These are NOT TdRs and must be REJECTED:
- Progress reports / annual reports / results reports
- Strategy documents (e.g. "Strategy 2024-2029")
- Brochures, flyers, newsletters, "at a glance" documents
- Presentations, slides, seminar proceedings, panelist notes
- User manuals, installation guides, catalogues
- Technical design documents, engineering specs
- Financial documents (mergers, acquisitions, ESG policies, fund reports)
- Procurement regulations or frameworks (general rules, NOT a specific call)
- Environmental plans (PGES, EIA)
- Academic research papers or journal articles
- Company data sheets or financial profiles
- Documents that simply mention "TDR" as an acronym for something else
  (e.g. "TDR Capital" = a hedge fund, "TDR" = Tropical Disease Research program)

Filename: {filename}

Document content (first 2000 chars):
---
{snippet}
---

You MUST answer with exactly one of:
ACCEPT: <one sentence explaining it IS a genuine consultant recruitment TdR>
REJECT: <one sentence explaining why it is NOT a consultant recruitment TdR>

Be STRICT. If you are not sure it is a genuine TdR, answer REJECT."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 100}
            },
            timeout=90
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()

        upper = answer.upper()
        if upper.startswith("ACCEPT"):
            reason = answer[6:].lstrip(":").strip()
            return True, f"LLM accepted: {reason}"
        elif upper.startswith("REJECT"):
            reason = answer[6:].lstrip(":").strip()
            return False, f"LLM rejected: {reason}"
        else:
            # Ambiguous → DEFAULT TO REJECT (stricter behavior)
            return False, f"LLM ambiguous — defaulting to REJECT: {answer[:100]}"

    except requests.exceptions.ConnectionError:
        return False, "Ollama not reachable — defaulting to REJECT"
    except Exception as e:
        return False, f"LLM error — defaulting to REJECT: {str(e)[:80]}"


# ============================================
# LOAD EXTRACTED DATA
# ============================================
print("=" * 60)
print("PHASE 0: STRICT TDR CLASSIFIER (v2)")
print("=" * 60)
print(f"\nLoading: {INPUT_FILE}")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    documents = json.load(f)

total = len(documents)
print(f"Found {total} extracted documents\n")
print("-" * 60)

accepted = []
rejected = []
report_entries = []

# ============================================
# CLASSIFY EACH DOCUMENT
# ============================================
for i, doc in enumerate(documents, 1):
    filename = doc.get("filename", "unknown")
    content  = doc.get("content", "")
    error    = doc.get("error", None)

    print(f"[{i:3}/{total}] {filename}")

    # Skip documents that failed extraction
    if error or not content:
        reason = f"Extraction failed: {error or 'empty content'}"
        print(f"        SKIP  {reason}\n")
        rejected.append(doc)
        report_entries.append({
            "filename": filename,
            "verdict": "REJECT",
            "method": "skip",
            "reason": reason,
            "score": None,
            "core_signals": 0
        })
        continue

    # --- Stage 1: Keyword Scoring ---
    score, pos_matches, neg_matches, core_count = score_document(content)

    # --- Gate: even with high score, need at least 1 core signal ---
    # This prevents false positives that just happen to have many generic words
    if score >= KEYWORD_ACCEPT_THRESHOLD and core_count >= 1:
        verdict = "ACCEPT"
        method  = "keyword"
        reason  = f"Score {score} with {core_count} core TdR signal(s) ({len(pos_matches)} positive)"
        print(f"        ACCEPT  [keywords, score={score}, core={core_count}]")

    elif score <= KEYWORD_REJECT_THRESHOLD:
        verdict = "REJECT"
        method  = "keyword"
        neg_labels = ', '.join(p[:50] for p in neg_matches[:3])
        reason  = f"Score {score} ({len(neg_matches)} negative signal(s): {neg_labels})"
        print(f"        REJECT  [keywords, score={score}]")

    elif score >= KEYWORD_ACCEPT_THRESHOLD and core_count == 0:
        # Has positive keywords but NO core TdR signal → very suspicious
        verdict = "REJECT"
        method  = "keyword_no_core"
        reason  = f"Score {score} but ZERO core TdR signals — not a genuine TdR"
        print(f"        REJECT  [good score={score} but no core signals]")

    else:
        # --- Stage 2: LLM for uncertain cases ---
        print(f"        ?? Uncertain [score={score}, core={core_count}] -> LLM...", end=" ", flush=True)
        is_tdr, llm_reason = ask_ollama(filename, content)
        verdict = "ACCEPT" if is_tdr else "REJECT"
        method  = "llm"
        reason  = llm_reason
        icon    = "ACCEPT" if is_tdr else "REJECT"
        print(f"{icon}")

    print(f"           {reason}\n")

    report_entries.append({
        "filename": filename,
        "verdict": verdict,
        "method": method,
        "reason": reason,
        "score": score,
        "core_signals": core_count
    })

    if verdict == "ACCEPT":
        accepted.append(doc)
    else:
        rejected.append(doc)

# ============================================
# SAVE OUTPUTS
# ============================================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(accepted, f, ensure_ascii=False, indent=2)

report = {
    "summary": {
        "total":    total,
        "accepted": len(accepted),
        "rejected": len(rejected),
    },
    "accepted": [e for e in report_entries if e["verdict"] == "ACCEPT"],
    "rejected": [e for e in report_entries if e["verdict"] == "REJECT"],
}
with open(REPORT_FILE, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# ============================================
# SUMMARY
# ============================================
print("=" * 60)
print("PHASE 0 COMPLETE — STRICT TDR CLASSIFICATION v2")
print("=" * 60)
print(f"   Total documents   : {total}")
print(f"   Accepted (TDR)    : {len(accepted)}")
print(f"   Rejected          : {len(rejected)}")
print(f"   Output JSON       : {OUTPUT_FILE}")
print(f"   Report            : {REPORT_FILE}")
print("=" * 60)
print("\n   Next step: phase2_clean.py")
