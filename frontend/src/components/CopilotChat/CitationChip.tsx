"use client";

import React, { useState } from "react";
import { VerificationDrawer } from "@/components/VerificationDrawer";
import styles from "./CitationChip.module.css";

interface Citation {
  citation_id: string;
  chunk_id: string;
  document_id: string;
  document_name: string;
  page: number | null;
  section: string;
  relevance_score: number;
  deep_link: string;
}

interface CitationChipProps {
  citation: Citation;
  index: number;
}

/**
 * Tappable citation chip linking to the source document (FR-3.1.2, FR-3.3.3).
 * Shows document name, page/section, and relevance score.
 */
export default function CitationChip({ citation, index }: CitationChipProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const pageInfo = citation.page ? `p.${citation.page}` : "";
  const sectionInfo = citation.section || "";
  const locationParts = [pageInfo, sectionInfo].filter(Boolean).join(" · ");

  return (
    <>
      <button
        onClick={() => setIsDrawerOpen(true)}
        className={styles.chip}
        title={`Verify ${citation.document_name}${locationParts ? ` - ${locationParts}` : ""}`}
        id={`citation-chip-${index}`}
        type="button"
      >
        <span className={styles.chipNumber}>[{index}]</span>
        <span className={styles.chipName}>{citation.document_name}</span>
        {locationParts && (
          <span className={styles.chipLocation}>{locationParts}</span>
        )}
      </button>

      {isDrawerOpen && (
        <VerificationDrawer 
          citationId={citation.citation_id} 
          onClose={() => setIsDrawerOpen(false)} 
        />
      )}
    </>
  );
}
