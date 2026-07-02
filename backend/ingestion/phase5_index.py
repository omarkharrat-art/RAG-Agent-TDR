import os
import json
import shutil
import fitz  # PyMuPDF
from pathlib import Path
import subprocess
import requests
import re
from collections import Counter

# ============================================
# CONFIGURATION
# ============================================

RAW_FOLDER = "backend/data/raw"
REJECTED_FOLDER = "backend/data/rejected"
REPORT_FILE = "backend/data/classification_report.json"
OLLAMA_MODEL = "mistral"

# TDR Keywords in Multiple Languages
TDR_KEYWORDS = {
    'en': ['terms of reference', 'tor', 'scope of work', 'deliverables', 
           'consultant', 'selection criteria', 'qualifications', 'objectives',
           'methodology', 'timeline', 'budget', 'rfp', 'request for proposal'],
    'fr': ['termes de référence', 'tdr', 'cahier des charges', 'appel d\'offres',
           'consultant', 'critères de sélection', 'qualifications', 'objectifs',
           'méthodologie', 'calendrier', 'budget', 'aof'],
    'ar': ['شروط المرجعية', 'دراسة', 'استشاري', 'معايير', 'مؤهلات',
           'أهداف', 'منهجية', 'جدول زمني'],
}

REJECTION_KEYWORDS = {
    'en': ['medical', 'clinical', 'research', 'academic', 'journal', 'article',
           'invoice', 'receipt', 'financial statement', 'contract', 'employment',
           'privacy policy', 'terms and conditions', 'published', 'peer-reviewed'],
    'fr': ['médical', 'clinique', 'recherche', 'académique', 'journal', 'article',
           'facture', 'reçu', 'déclaration financière', 'contrat', 'emploi'],
}

# Create only these two folders
Path(RAW_FOLDER).mkdir(parents=True, exist_ok=True)
Path(REJECTED_FOLDER).mkdir(parents=True, exist_ok=True)

# ============================================
# OLLAMA UTILITIES
# ============================================

def check_ollama_running():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_ollama():
    print("🦙 Starting Ollama...")
    try:
        subprocess.Popen(['ollama', 'serve'])
        print("✅ Ollama started (wait 5-10 seconds)")
        return True
    except Exception as e:
        print(f"❌ Could not start Ollama: {e}")
        return False

def pull_model(model_name):
    try:
        response = requests.post(
            f"http://localhost:11434/api/pull",
            json={"name": model_name},
            timeout=600
        )
        if response.status_code == 200:
            print(f"✅ Model '{model_name}' ready")
            return True
    except Exception as e:
        print(f"❌ Error pulling model: {e}")
    return False

def query_ollama(prompt, model=OLLAMA_MODEL):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2,
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()
        else:
            print(f"❌ Ollama error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ollama error: {e}")
        return None

# ============================================
# TEXT EXTRACTION
# ============================================

def extract_text_from_pdf(pdf_path, num_pages=10):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        metadata = doc.metadata
        
        pages_to_read = min(num_pages, len(doc))
        for page_num in range(pages_to_read):
            page = doc[page_num]
            text += page.get_text() + "\n"
        
        doc.close()
        return text.strip(), metadata
    except Exception as e:
        print(f"      ❌ Error reading PDF: {e}")
        return "", {}

def extract_images_from_pdf(pdf_path, max_images=3):
    try:
        doc = fitz.open(pdf_path)
        images_found = []
        
        for page_num in range(min(5, len(doc))):
            page = doc[page_num]
            image_list = page.get_images()
            
            if image_list and len(images_found) < max_images:
                for img_index in image_list[:2]:
                    xref = img_index[0]
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha < 4:
                        images_found.append((page_num, xref))
                        if len(images_found) >= max_images:
                            break
        
        doc.close()
        return len(images_found) > 0
    except Exception as e:
        return False

# ============================================
# KEYWORD ANALYSIS
# ============================================

def score_keywords(text):
    text_lower = text.lower()
    
    tdr_score = 0
    for lang_keywords in TDR_KEYWORDS.values():
        tdr_score += sum(text_lower.count(kw) for kw in lang_keywords)
    
    reject_score = 0
    for lang_keywords in REJECTION_KEYWORDS.values():
        reject_score += sum(text_lower.count(kw) for kw in lang_keywords)
    
    return tdr_score, reject_score

def detect_document_structure(text):
    sections = [
        r'(scope|objectif|objective)',
        r'(deliverable|livrable)',
        r'(qualif|profile|requirement)',
        r'(timeline|calendrier|schedule)',
        r'(budget|cost|price)',
        r'(methodology|méthodologie)',
        r'(selection criteria|critère)',
    ]
    
    found_sections = sum(1 for pattern in sections if re.search(pattern, text.lower()))
    return found_sections

# ============================================
# LLM CLASSIFICATION
# ============================================

def classify_with_llm(text, filename, tdr_score, reject_score):
    if not text or len(text) < 300:
        return "REJECT", "Insufficient text", 0.1
    
    if reject_score > 5:
        return "REJECT", "Contains rejection keywords", 0.1
    
    prompt = f"""TASK: Classify if this is a Terms of Reference (TDR) document.

DEFINITION OF TDR:
A TDR is an official project scope document that defines:
- Consultant/expert selection and qualifications
- Project objectives and scope
- Required deliverables
- Timeline and budget
- Evaluation criteria
- Project requirements

NOT a TDR:
- Medical/clinical research
- Academic papers/journals
- Invoices/receipts
- Employment contracts
- Published articles
- Product manuals or catalogs
- Equipment user manuals
- Assembly instructions
- TDR Programme documents (Tropical Disease Research)

DOCUMENT: {filename}

TEXT SAMPLE (first 1500 chars):
{text[:1500]}

YOUR TASK:
1. Is this a TDR or similar project scope document? YES or NO
2. Confidence: HIGH, MEDIUM, or LOW

RESPOND EXACTLY in this format:
DECISION: [YES or NO]
CONFIDENCE: [HIGH or MEDIUM or LOW]
REASON: [one sentence]"""

    response = query_ollama(prompt)
    
    if response:
        decision = "ACCEPT" if "YES" in response.upper() else "REJECT"
        confidence = 0.9 if "HIGH" in response.upper() else 0.6 if "MEDIUM" in response.upper() else 0.3
        return decision, response[:100], confidence
    else:
        return "REJECT", "LLM failed", 0.0

# ============================================
# MAIN CLASSIFICATION - FILENAME CHECK FIRST!
# ============================================

def classify_document(pdf_path, filename):
    """
    CRITICAL: Check filename FIRST before extracting text!
    This prevents issues with large/corrupted PDFs.
    """
    
    print(f"\n  📄 {filename}")
    filename_lower = filename.lower()
    
    # ============================================
    # STEP 1: CHECK FILENAME FOR TDR INDICATORS
    # ============================================
    
    # TDR variations and indicators in filename
    tdr_filename_indicators = [
        'tdr', 'tor', 
        'terme de reference', 'terms of reference',
        'termes de reference', 'termes-de-reference',
        'terme-de-reference', 'termes-de-ref',
        'cahier des charges', 'cahier-de-charges',
        'appel d\'offres', 'appel doffres', 'appel-doffres',
        'rfp', 'aof', 'reference', 'ref',
        'consultation', 'projet', 'project',
        'selection', 'auditeur', 'audit',
        'prestation', 'service'
    ]
    
    # Check if filename contains any TDR indicator
    for indicator in tdr_filename_indicators:
        if indicator in filename_lower:
            # Check for false positives (product manuals, catalogs, etc.)
            false_positives = [
                'manual', 'user manual', 'manuel utilisateur',
                'assembly', 'montage', 'installation',
                'rotisserie', 'tent', 'marquee', 'tente',
                'catalogue', 'catalog', 'brochure', 'certificat',
                'specification', 'technical', 'technique'
            ]
            
            is_false_positive = False
            for fp in false_positives:
                if fp in filename_lower:
                    is_false_positive = True
                    break
            
            if not is_false_positive:
                print(f"     ✅ FILENAME contains '{indicator}' - ACCEPT")
                return "ACCEPT", f"Filename contains '{indicator}'", 1.0
            else:
                print(f"     ⚠️  Contains '{indicator}' but looks like false positive")
                # Continue to text extraction to verify
    
    # ============================================
    # STEP 2: EXTRACT TEXT (only if filename didn't match)
    # ============================================
    
    print(f"     📖 Extracting text...")
    text, metadata = extract_text_from_pdf(pdf_path, num_pages=10)
    
    if not text or len(text) < 300:
        print(f"     ❌ Insufficient text ({len(text)} chars)")
        return "REJECT", "Insufficient text", 0.1
    
    # ============================================
    # STEP 3: CHECK TEXT FOR TDR PROGRAMME DOCUMENTS
    # ============================================
    
    # Check if it's about the TDR Programme (Tropical Disease Research)
    tdr_programme_indicators = [
        r'tdr\s+(?:special\s+programme|programme\s+for\s+research)',
        r'unicef/undp/world\s+bank/who',
        r'special\s+programme\s+for\s+research\s+and\s+training',
        r'joint\s+coordinating\s+board',
        r'scientific\s+and\s+technical\s+advisory',
        r'tdr\'s\s+(?:work|activities|strategy|portfolio)',
        r'tdr-supported\s+research',
    ]
    
    text_sample = text[:2000].lower()
    for pattern in tdr_programme_indicators:
        if re.search(pattern, text_sample, re.IGNORECASE):
            print(f"     ❌ Document is about TDR Programme, not Terms of Reference")
            return "REJECT", "TDR Programme document", 0.1
    
    # ============================================
    # STEP 4: CHECK FOR PRODUCT MANUALS
    # ============================================
    
    product_indicators = [
        r'user\s+manual',
        r'manuel\s+utilisateur',
        r'assembly\s+instructions',
        r'notice\s+de\s+montage',
        r'installation\s+instructions',
        r'safety\s+warnings',
        r'rotisserie',
        r'tent',
        r'marquee',
        r'specifications?',
        r'technical\s+data',
        r'operating\s+instructions',
    ]
    
    for pattern in product_indicators:
        if re.search(pattern, text_sample, re.IGNORECASE):
            print(f"     ❌ Document appears to be a product manual/catalog")
            return "REJECT", "Product manual or catalog", 0.1
    
    # ============================================
    # STEP 5: KEYWORD SCORING
    # ============================================
    
    print(f"     🔍 Analyzing keywords...")
    tdr_score, reject_score = score_keywords(text)
    struct_score = detect_document_structure(text)
    
    print(f"     📊 TDR: {tdr_score} | Reject: {reject_score} | Structure: {struct_score}")
    
    if tdr_score >= 8 and reject_score <= 2:
        print(f"     ✅ Strong TDR signals - ACCEPT")
        return "ACCEPT", f"Strong keyword signals", 0.85
    
    if reject_score >= 8:
        print(f"     ❌ Strong rejection signals")
        return "REJECT", f"High rejection score ({reject_score})", 0.80
    
    # ============================================
    # STEP 6: IMAGE ANALYSIS
    # ============================================
    
    print(f"     🖼️  Checking for images...")
    has_images = extract_images_from_pdf(pdf_path)
    confidence_score = 0.0
    if has_images:
        print(f"     📸 Document contains images")
        confidence_score += 0.15
    
    # ============================================
    # STEP 7: LLM CLASSIFICATION
    # ============================================
    
    print(f"     🤖 LLM analysis...")
    result, reason, llm_confidence = classify_with_llm(text, filename, tdr_score, reject_score)
    
    final_confidence = (llm_confidence + confidence_score) / 2 if confidence_score > 0 else llm_confidence
    final_confidence = min(max(final_confidence, 0.1), 0.95)
    
    if result == "ACCEPT":
        print(f"     ✅ {reason}")
    else:
        print(f"     ❌ {reason}")
    
    return result, reason, final_confidence

# ============================================
# FILE MANAGEMENT
# ============================================

def move_to_rejected(source_path, filename):
    """Move rejected file to rejected folder"""
    dest_path = os.path.join(REJECTED_FOLDER, filename)
    
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(REJECTED_FOLDER, f"{base}_{counter}{ext}")
            counter += 1
    
    shutil.move(source_path, dest_path)
    return dest_path

# ============================================
# REPORTING
# ============================================

def save_report(results):
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📊 Report saved to: {REPORT_FILE}")

def print_summary(results):
    total = len(results['accepted']) + len(results['rejected'])
    accepted_pct = (len(results['accepted']) / total * 100) if total > 0 else 0
    
    print("\n" + "=" * 90)
    print(f"{'🦙 TDR CLASSIFIER - RESULTS':^90}")
    print("=" * 90)
    print(f"✅ TDRs (stay in RAW):     {len(results['accepted']):3d} / {total:3d}  ({accepted_pct:5.1f}%)")
    print(f"❌ Non-TDRs (to REJECTED): {len(results['rejected']):3d} / {total:3d}  ({100-accepted_pct:5.1f}%)")
    print("=" * 90)
    
    if results['accepted']:
        print(f"\n✅ TDRs - STAY IN RAW ({len(results['accepted'])} files):")
        for item in results['accepted'][:15]:
            print(f"   • {item['filename']}")
            print(f"     → {item['reason']}")
        if len(results['accepted']) > 15:
            print(f"   ... and {len(results['accepted']) - 15} more")
    
    if results['rejected']:
        print(f"\n❌ NON-TDRs - MOVED TO REJECTED ({len(results['rejected'])} files):")
        for item in results['rejected'][:15]:
            print(f"   • {item['filename']}")
            print(f"     → {item['reason']}")
        if len(results['rejected']) > 15:
            print(f"   ... and {len(results['rejected']) - 15} more")
    
    print("\n" + "=" * 90)

# ============================================
# MAIN
# ============================================

def main():
    print("\n" + "=" * 90)
    print(f"{'🦙 TDR CLASSIFIER v3.0':^90}")
    print(f"{'RAW → REJECTED (TDR stays in RAW)':^90}")
    print("=" * 90)
    print("   📌 STEP 1: Check FILENAME for TDR indicators")
    print("      - tdr, tor, terms of reference, etc.")
    print("      - appel d'offres, cahier des charges, etc.")
    print("   📌 STEP 2: Only then extract text and classify")
    print("   ✅ TDR → stays in RAW folder")
    print("   ❌ Non-TDR → moves to REJECTED folder")
    print("=" * 90)
    
    # Check/start Ollama
    print("\n🔍 Checking Ollama connection...")
    if not check_ollama_running():
        print("⚠️  Ollama is not running")
        if input("Start Ollama now? (yes/no): ").lower() == "yes":
            if not start_ollama():
                print("❌ Could not start Ollama")
                print("   Run: ollama serve")
                return
            input("Press Enter after Ollama is ready... ")
        else:
            return
    
    print("✅ Ollama is running")
    
    # Check model
    print(f"\n📥 Checking model '{OLLAMA_MODEL}'...")
    if not pull_model(OLLAMA_MODEL):
        print(f"⚠️  Could not pull model")
        return
    
    # Check raw folder
    if not os.path.exists(RAW_FOLDER):
        print(f"\n❌ Error: Folder not found: {RAW_FOLDER}")
        return
    
    # Get PDF files only from raw
    pdf_files = [f for f in os.listdir(RAW_FOLDER) if f.lower().endswith(".pdf")]
    print(f"\n🔍 Found {len(pdf_files)} PDF files in RAW folder")
    
    if not pdf_files:
        print("⚠️  No PDFs found")
        return
    
    response = input(f"\n▶️  Classify {len(pdf_files)} documents? (yes/no): ").strip().lower()
    if response != "yes":
        print("⚠️  Aborted.")
        return
    
    print("\n⏱️  Processing...\n")
    
    results = {"accepted": [], "rejected": []}
    
    for idx, filename in enumerate(pdf_files, 1):
        source_path = os.path.join(RAW_FOLDER, filename)
        print(f"[{idx}/{len(pdf_files)}]", end="")
        
        result, reason, confidence = classify_document(source_path, filename)
        
        if result == "ACCEPT":
            results["accepted"].append({
                "filename": filename,
                "reason": reason,
                "confidence": confidence
            })
        else:
            move_to_rejected(source_path, filename)
            results["rejected"].append({
                "filename": filename,
                "reason": reason,
                "confidence": confidence
            })
    
    save_report(results)
    print_summary(results)
    
    print("\n" + "=" * 90)
    print("✅ Classification complete!")
    print(f"   ✅ TDRs stay in: {RAW_FOLDER}")
    print(f"   ❌ Non-TDRs moved to: {REJECTED_FOLDER}")
    print("=" * 90)

if __name__ == "__main__":
    main()