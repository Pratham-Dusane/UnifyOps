import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

import dotenv
dotenv.load_dotenv(dotenv_path=backend_dir / ".env")
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    sa_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    if not os.path.isabs(sa_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((backend_dir / sa_path).resolve())

from app.core.config import settings

# Force reimport with fixed env
from app.services.document_ai import document_ai_service
from app.services.gemini import gemini_service

print("=== DIAGNOSTICS ===")
print(f"GOOGLE_APPLICATION_CREDENTIALS exists: {os.path.exists(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', ''))}")
print(f"DocumentAI Enabled: {document_ai_service.enabled}")
print(f"Gemini Enabled: {gemini_service.enabled}")

# Test 1: Gemini entity extraction
print("\n--- Test 1: Gemini Entity Extraction ---")
try:
    entities = gemini_service.extract_entities(
        "Maintenance work order for pump P-204A. Scheduled date 2025-06-15. "
        "Technician Rajesh Kumar found seal leakage due to mechanical degradation. "
        "Material required: John Crane Type 2100 seal kit. Location: Unit 3 CDU.",
        "work_order"
    )
    if entities:
        print(f"SUCCESS! Got {len(entities)} entities:")
        for e in entities[:5]:
            print(f"  - {e.get('entity_type')}: {e.get('value')} ({e.get('confidence')})")
    else:
        print("FAILED: Got empty list (API call likely failed, check logs above)")
except Exception as e:
    print(f"EXCEPTION: {e}")

# Test 1.5: Groq fallback entity extraction
print("\n--- Test 1.5: Groq Fallback Entity Extraction ---")
try:
    entities = gemini_service.extract_entities_via_groq(
        "Maintenance work order for pump P-204A. Scheduled date 2025-06-15. "
        "Technician Rajesh Kumar found seal leakage due to mechanical degradation. "
        "Material required: John Crane Type 2100 seal kit. Location: Unit 3 CDU.",
        "work_order"
    )
    if entities:
        print(f"SUCCESS! Got {len(entities)} entities via Groq:")
        for e in entities[:5]:
            print(f"  - {e.get('entity_type')}: {e.get('value')} ({e.get('confidence')})")
    else:
        print("FAILED: Groq returned empty list or None")
except Exception as e:
    print(f"EXCEPTION: {e}")

# Test 2: Document AI OCR on your actual sample PDF
print("\n--- Test 2: Document AI OCR ---")
sample = backend_dir / "samples" / "boiler maintainance.pdf"
if sample.exists():
    try:
        content = sample.read_bytes()
        result = document_ai_service.extract_layout(content, "application/pdf")
        pages = result.get("page_count", 0)
        text = result.get("text", "")
        print(f"SUCCESS! Pages: {pages}, Text length: {len(text)} chars")
        print(f"First 200 chars: {text[:200]}")
    except Exception as e:
        print(f"EXCEPTION: {e}")
else:
    print(f"Sample file not found: {sample}")

# Test 3: Document AI Classification
print("\n--- Test 3: Document AI Classification ---")
if sample.exists():
    try:
        content = sample.read_bytes()
        doc_type, confidence = document_ai_service.classify_document(content, "application/pdf")
        print(f"Classified as: {doc_type} with confidence: {confidence}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

print("\n=== DONE ===")
