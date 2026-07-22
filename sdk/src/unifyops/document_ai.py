"""
Document Processing & Entity Extraction Engine for UnifyOps SDK.
"""

import re
import uuid
from typing import List, Optional
from unifyops.models import (
    Document,
    DocumentChunk,
    DocumentType,
    EntityCategory,
    EntityNode,
)
from unifyops.store import KnowledgeStore


class DocumentProcessor:
    """Ingests documents, chunks text, and extracts plant entity tags into the graph."""

    def __init__(self, store: KnowledgeStore) -> None:
        self.store = store

    def process_text(
        self,
        text: str,
        filename: str,
        org_id: str,
        document_type: DocumentType = DocumentType.OTHER,
        plant_id: Optional[str] = None,
        department: Optional[str] = None,
        chunk_size: int = 400,
    ) -> Document:
        """
        Process document text, extract entity tags, store chunks and graph nodes.
        """
        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            org_id=org_id,
            title=filename,
            document_type=document_type,
            original_filename=filename,
            file_size_bytes=len(text.encode("utf-8")),
            plant_id=plant_id,
            department=department,
        )
        self.store.add_document(doc)

        # Basic text chunking
        raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks_text: List[str] = []
        current_chunk = ""

        for p in raw_paragraphs:
            if len(current_chunk) + len(p) <= chunk_size:
                current_chunk = (current_chunk + "\n\n" + p).strip()
            else:
                if current_chunk:
                    chunks_text.append(current_chunk)
                current_chunk = p

        if current_chunk:
            chunks_text.append(current_chunk)

        if not chunks_text:
            chunks_text = [text]

        # Extract entities from document text
        equipment_tags = self._extract_equipment_tags(text)
        regulatory_tags = self._extract_regulatory_tags(text)

        entity_ids: List[str] = []
        for tag in equipment_tags:
            entity = EntityNode(
                id=f"ent-{tag}",
                org_id=org_id,
                name=tag,
                category=EntityCategory.EQUIPMENT,
                value=tag,
                normalised_value=tag.replace("-", "").upper(),
                linked_document_ids=[doc_id],
            )
            self.store.add_entity(entity)
            entity_ids.append(entity.id)

        for tag in regulatory_tags:
            entity = EntityNode(
                id=f"ent-reg-{tag.replace(' ', '_')}",
                org_id=org_id,
                name=tag,
                category=EntityCategory.REGULATORY_CLAUSE,
                value=tag,
                normalised_value=tag.upper(),
                linked_document_ids=[doc_id],
            )
            self.store.add_entity(entity)
            entity_ids.append(entity.id)

        # Save document chunks
        for idx, chunk_str in enumerate(chunks_text):
            chunk = DocumentChunk(
                id=f"{doc_id}-chunk-{idx + 1}",
                document_id=doc_id,
                org_id=org_id,
                chunk_index=idx + 1,
                text=chunk_str,
                source_page=idx + 1,
                entity_ids=entity_ids,
            )
            self.store.add_chunk(chunk)

        return doc

    def _extract_equipment_tags(self, text: str) -> List[str]:
        tags = re.findall(r"\b[A-Z]{1,4}-\d{2,4}[A-Z]?\b", text.upper())
        return list(set(tags))

    def _extract_regulatory_tags(self, text: str) -> List[str]:
        regs = re.findall(r"\b(?:OISD|API|PNGRB|ISO)[-\s][\w\d-]+\b", text.upper())
        return list(set(regs))
