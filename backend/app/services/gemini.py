"""
UnifyOps - Gemini Studio Service

Integrates with Google AI Studio (using GEMINI_API_KEY) (FR-1.5, FR-1.6).
Features:
- Entity extraction from OCR texts based on document types (FR-1.5.1).
- Structured JSON output constrained to ontology schema.
- Vector embeddings generation using models/text-embedding-004 (FR-1.6.2).
"""

import json
import google.generativeai as genai
from app.core.config import settings


class GeminiService:
    """Manages Gemini Studio AI integrations for extraction and embeddings."""

    def __init__(self) -> None:
        self.enabled = False
        api_key = settings.gemini_api_key

        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.enabled = True
            except Exception as e:
                print(
                    f"[GeminiService] Failed to configure Gemini API client: {e}. Falling back to simulation."
                )
        else:
            print(
                "[GeminiService] GEMINI_API_KEY not set. Running in simulation/fallback mode."
            )

    def extract_entities(self, doc_text: str, doc_type: str) -> list[dict]:
        """
        Invokes Gemini 2.0 Flash in JSON mode to extract structured entities (FR-1.5.1).
        Falls back to Groq, then regex if Gemini is rate-limited or disabled.
        Always merges regex-detected entities to catch tags the LLM might miss.
        """
        llm_entities = []

        if self.enabled:
            try:
                model = genai.GenerativeModel("gemini-2.0-flash")
                prompt = self._build_extraction_prompt(doc_text, doc_type)

                response = model.generate_content(
                    prompt, generation_config={"response_mime_type": "application/json"}
                )

                try:
                    entities = json.loads(response.text)
                    if isinstance(entities, list):
                        llm_entities = entities
                    elif isinstance(entities, dict) and "entities" in entities:
                        llm_entities = entities["entities"]
                except Exception as parse_err:
                    print(
                        f"[GeminiService] Failed to parse Gemini extraction JSON response: {parse_err}. Raw text: {response.text}"
                    )
            except Exception as e:
                print(f"[GeminiService] Gemini Entity Extraction failed: {e}")

        # Fallback 1: Try Groq API if Gemini returned nothing
        if not llm_entities:
            groq_entities = self.extract_entities_via_groq(doc_text, doc_type)
            if groq_entities is not None:
                print(
                    f"[GeminiService] Successfully extracted {len(groq_entities)} entities via Groq."
                )
                llm_entities = groq_entities

        # Always run regex to catch equipment tags/dates/regulations the LLM might miss
        regex_entities = self._extract_regex_entities(doc_text)

        # Merge: add regex entities whose values aren't already in the LLM results
        existing_values = {e.get("value", "").upper() for e in llm_entities}
        for re_ent in regex_entities:
            if re_ent["value"].upper() not in existing_values:
                llm_entities.append(re_ent)
                existing_values.add(re_ent["value"].upper())

        if llm_entities:
            print(
                f"[GeminiService] Total entities after merge: {len(llm_entities)} (LLM + regex)"
            )

        return llm_entities

    def _extract_regex_entities(self, doc_text: str) -> list[dict]:
        """Extract equipment tags, dates, and regulatory refs via regex patterns."""
        import re

        entities = []

        # Equipment tags: P-204A, HE-301, PSV-301A, V-102, M-08 etc.
        tags = re.findall(r"\b[A-Z]{1,4}-\d{2,4}[A-Z]?\b", doc_text)
        for t in set(tags):
            entities.append(
                {
                    "entity_type": "equipment_tag",
                    "value": t,
                    "normalised_value": t.upper().replace(" ", "_"),
                    "confidence": 0.90,
                }
            )

        # Dates: 2025-06-15, 7/7/86
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", doc_text)
        for d in set(dates):
            entities.append(
                {
                    "entity_type": "date",
                    "value": d,
                    "normalised_value": d,
                    "confidence": 0.95,
                }
            )

        # Regulatory clauses: OISD-STD-154, API 510, PNGRB-xxx
        regs = re.findall(r"\b(?:OISD|API|PNGRB)[-\s][\w\d-]+\b", doc_text)
        for r in set(regs):
            entities.append(
                {
                    "entity_type": "regulatory_clause",
                    "value": r.strip(),
                    "normalised_value": r.strip().upper().replace(" ", "_"),
                    "confidence": 0.92,
                }
            )

        return entities

    def _build_extraction_prompt(self, doc_text: str, doc_type: str) -> str:
        """Build a grounded entity extraction prompt that prevents hallucination."""
        return f"""You are a precise entity extractor for industrial plant documentation.
Your task: extract entities from the document text below.

CRITICAL RULES:
1. Every entity "value" MUST be a VERBATIM quote copied exactly from the document text.
2. Do NOT invent, infer, or hallucinate entities that are not explicitly written in the text.
3. Do NOT use example values from these instructions as entity values.
4. If the text contains very few extractable entities, return a short list. An empty list is acceptable.
5. For equipment_tag: only extract actual tag IDs like "P-201", "HE-301", "V-102", "M-08" - alphanumeric codes that appear in the text.
6. For procedure_step: only extract if the text explicitly describes a step-by-step procedure.
7. Confidence should reflect how clearly the entity appears in the text (0.95 for exact clear matches, lower for ambiguous ones).

Document type: '{doc_type}'

Allowed entity types:
- equipment_tag: Equipment tag IDs (e.g. P-204A, HE-301, PSV-301A)
- location: Physical locations mentioned (e.g. Unit 3, Boiler House)
- date: Dates in any format
- person: Named individuals or specific role titles
- regulatory_clause: Standards/regulations with clause numbers
- document_reference: Referenced document IDs or titles
- failure_mode: Specific failure descriptions
- procedure_step: Explicit numbered/ordered procedure steps
- material: Specific material grades or part names
- measurement: Numerical measurements with units

Return ONLY a JSON object with key "entities" containing a list. Each entity:
- entity_type: (one of the types above)
- value: (EXACT verbatim quote from the text)
- normalised_value: (uppercase normalised form)
- confidence: (float 0.0-1.0)
- review_reason: (string or null)

=== DOCUMENT TEXT (first 8000 chars) ===
{doc_text[:8000]}
=== END DOCUMENT TEXT ==="""

    def extract_entities_via_groq(
        self, doc_text: str, doc_type: str
    ) -> list[dict] | None:
        """Fallback extraction using Groq (llama-3.3-70b-versatile in JSON mode)."""
        api_key = settings.groq_api_key
        if not api_key:
            return None

        try:
            prompt = self._build_extraction_prompt(doc_text, doc_type)

            import httpx

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
            }

            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20.0,
            )

            if response.status_code == 200:
                res_data = response.json()
                content_str = res_data["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "entities" in parsed:
                    return parsed["entities"]
            else:
                print(
                    f"[GroqFallback] Groq API returned status {response.status_code}: {response.text}"
                )
        except Exception as e:
            print(f"[GroqFallback] Groq API Call failed: {e}")

        return None

    def generate_embeddings(self, text_chunks: list[str]) -> list[list[float]] | None:
        """
        Generates vector embeddings using text-embedding-004 (FR-1.6.2).
        """
        if self.enabled and text_chunks:
            try:
                response = genai.embed_content(
                    model="models/gemini-embedding-exp-03-07",
                    content=text_chunks,
                    task_type="retrieval_document",
                )
                if "embedding" in response:
                    return response["embedding"]  # type: ignore
            except Exception as e:
                print(f"[GeminiService] Gemini Embeddings call failed: {e}")

        # Fallback: skip embeddings (not critical for pipeline completion)
        return None

    def classify_text_via_groq(self, text: str, filename: str) -> tuple[str, float]:
        """
        Classify document type using Groq LLM based on OCR text content.
        Returns (doc_type_value, confidence).
        """
        api_key = settings.groq_api_key
        if not api_key or not text.strip():
            return ("unknown", 0.0)

        try:
            prompt = f"""You are an expert document classifier for industrial plant documentation.
            
            Classify the following document into EXACTLY ONE of these categories:
            - engineering_drawing (P&ID diagrams, piping layouts, instrument diagrams, process flow diagrams)
            - work_order (maintenance work orders, job cards, service requests)
            - safety_procedure (SOPs, safety manuals, operating procedures, safety guidelines)
            - inspection_report (inspection reports, condition assessments, audit reports)
            - operating_instruction (operating manuals, startup/shutdown procedures)
            - incident_report (incident reports, accident reports, near-miss reports)
            - regulatory (regulatory documents, compliance standards, OISD/API standards)
            - unknown (if none of the above fit)
            
            Filename: {filename}
            
            Document text (first 3000 chars):
            \"\"\"{text[:3000]}\"\"\"
            
            Return ONLY a JSON object with these keys:
            - doc_type: (string, one of the categories above)
            - confidence: (float between 0.0 and 1.0)
            - reasoning: (string, brief explanation)
            """

            import httpx

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }

            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=10.0,
            )

            if response.status_code == 200:
                res_data = response.json()
                content_str = res_data["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                doc_type = parsed.get("doc_type", "unknown")
                confidence = float(parsed.get("confidence", 0.85))
                print(
                    f"[GroqClassifier] Classified as '{doc_type}' with confidence {confidence}: {parsed.get('reasoning', '')}"
                )
                return (doc_type, confidence)
            else:
                print(
                    f"[GroqClassifier] Groq returned status {response.status_code}: {response.text}"
                )
        except Exception as e:
            print(f"[GroqClassifier] Classification failed: {e}")

        return ("unknown", 0.0)


gemini_service = GeminiService()
