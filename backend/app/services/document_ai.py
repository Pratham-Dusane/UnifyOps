"""
UnifyOps — Document AI Service

Integrates with Google Cloud Document AI (FR-1.2, FR-1.3, FR-1.4).
Features:
- Document Auto-classification (FR-1.2.1)
- Text, Layout, and Table OCR extraction (FR-1.3.1)
- Custom P&ID Equipment Tag extraction (FR-1.4.1)
"""

import os
from google.cloud import documentai
from app.core.config import settings
from app.models.ingestion import DocumentType


class DocumentAIService:
    """Manages GCP Document AI api interactions with local fallbacks."""

    def __init__(self) -> None:
        self.enabled = False

        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                # Document AI endpoint requires setting api_endpoint for specific regions
                # For asia-south region, use 'asia-south-documentai.googleapis.com' or global
                location = settings.gcp_location
                api_endpoint = f"{location}-documentai.googleapis.com" if location != "global" else "documentai.googleapis.com"
                
                client_options = {"api_endpoint": api_endpoint}
                self.client = documentai.DocumentProcessorServiceClient(client_options=client_options)
                self.enabled = True
            except Exception as e:
                print(f"[DocumentAIService] Failed to initialize Document AI client: {e}. Running in simulation/fallback mode.")
        else:
            print("[DocumentAIService] GCP credentials not set. Running in simulation/fallback mode.")

    def classify_document(self, file_content: bytes, mime_type: str) -> tuple[DocumentType, float]:
        """
        Classifies a document into one of the 7 core types using Custom Classifier (FR-1.2.1).
        Returns (DocumentType, confidence_score).
        """
        if self.enabled and settings.docai_classifier_processor_id:
            try:
                raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
                request = documentai.ProcessRequest(
                    name=settings.docai_classifier_processor_path,
                    raw_document=raw_document
                )
                result = self.client.process_document(request=request, timeout=10.0)
                document = result.document

                # Custom Classifiers return classes under entities
                if document.entities:
                    # Sort by confidence descending
                    sorted_entities = sorted(document.entities, key=lambda e: e.confidence, reverse=True)
                    top_entity = sorted_entities[0]
                    
                    # Map top entity type to DocumentType enum
                    try:
                        return DocumentType(top_entity.type_), float(top_entity.confidence)
                    except ValueError:
                        # Fallback if class name matches with slight variation
                        clean_type = top_entity.type_.lower().replace(" ", "_")
                        try:
                            return DocumentType(clean_type), float(top_entity.confidence)
                        except ValueError:
                            pass
                return DocumentType.UNKNOWN, 1.0
            except Exception as e:
                print(f"[DocumentAIService] Document Classification API call failed: {e}")

        # Fallback simulation
        return DocumentType.UNKNOWN, 0.0

    def extract_layout(self, file_content: bytes, mime_type: str) -> dict:
        """
        Processes document using Document OCR/Layout processor (FR-1.3.1).
        Extracts structural text blocks, tables, and page count.
        """
        if self.enabled and settings.docai_ocr_processor_id:
            try:
                raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
                request = documentai.ProcessRequest(
                    name=settings.docai_ocr_processor_path,
                    raw_document=raw_document
                )
                result = self.client.process_document(request=request, timeout=15.0)
                document = result.document

                # Extract tabular structured data (FR-1.3.2)
                tables = []
                for page in document.pages:
                    for table in page.tables:
                        table_data = []
                        # Extract header rows if present
                        for row in table.header_rows:
                            row_cells = []
                            for cell in row.cells:
                                # Get cell text segment
                                cell_text = "".join([document.text[seg.start_index:seg.end_index] for seg in cell.layout.text_anchor.text_segments]).strip()
                                row_cells.append(cell_text)
                            table_data.append({"type": "header", "cells": row_cells})

                        # Extract body rows
                        for row in table.body_rows:
                            row_cells = []
                            for cell in row.cells:
                                cell_text = "".join([document.text[seg.start_index:seg.end_index] for seg in cell.layout.text_anchor.text_segments]).strip()
                                row_cells.append(cell_text)
                            table_data.append({"type": "body", "cells": row_cells})
                        tables.append(table_data)

                # Extract page-by-page paragraph texts with heading structures
                page_texts = []
                for idx, page in enumerate(document.pages):
                    # Group paragraphs by reading order
                    for paragraph in page.paragraphs:
                        para_text = "".join([document.text[seg.start_index:seg.end_index] for seg in paragraph.layout.text_anchor.text_segments]).strip()
                        if para_text:
                            page_texts.append(para_text)

                return {
                    "text": document.text,
                    "page_count": len(document.pages),
                    "tables": tables,
                    "page_texts": page_texts
                }
            except Exception as e:
                print(f"[DocumentAIService] Document OCR API call failed: {e}")

        # Fallback simulation
        return {
            "text": "",
            "page_count": 0,
            "tables": [],
            "page_texts": []
        }

    def extract_pid_tags(self, file_content: bytes, mime_type: str) -> list[dict]:
        """
        Processes P&ID drawing with Custom Extractor (FR-1.4.1).
        Extracts equipment tag labels with bounding boxes.
        """
        if self.enabled and settings.docai_pid_extractor_processor_id:
            try:
                raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)
                request = documentai.ProcessRequest(
                    name=settings.docai_pid_extractor_processor_path,
                    raw_document=raw_document
                )
                result = self.client.process_document(request=request, timeout=10.0)
                document = result.document

                tags = []
                for entity in document.entities:
                    # Bounding box coordinates from normalized vertices
                    bbox = None
                    if entity.page_anchor and entity.page_anchor.page_refs:
                        pref = entity.page_anchor.page_refs[0]
                        if pref.bounding_poly and pref.bounding_poly.normalized_vertices:
                            vertices = pref.bounding_poly.normalized_vertices
                            xs = [v.x for v in vertices]
                            ys = [v.y for v in vertices]
                            bbox = [min(xs), min(ys), max(xs), max(ys)]

                    tags.append({
                        "value": entity.mention_text or entity.normalized_value.text or "",
                        "type": entity.type_,
                        "confidence": float(entity.confidence),
                        "bounding_box": bbox,
                        "source_page": int(pref.page) + 1 if pref else 1
                    })
                return tags
            except Exception as e:
                print(f"[DocumentAIService] Custom Extractor P&ID API call failed: {e}")

        return []


document_ai_service = DocumentAIService()
