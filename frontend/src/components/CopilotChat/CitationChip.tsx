"use client";

import React from "react";
import Link from "next/link";
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
  const pageInfo = citation.page ? `p.${citation.page}` : "";
  const sectionInfo = citation.section || "";
  const locationParts = [pageInfo, sectionInfo].filter(Boolean).join(" · ");

  return (
    <Link
      href={`/documents/${citation.document_id}`}
      className={styles.chip}
      title={`Open ${citation.document_name}${locationParts ? ` - ${locationParts}` : ""}`}
      id={`citation-chip-${index}`}
    >
      <span className={styles.chipNumber}>[{index}]</span>
      <span className={styles.chipName}>{citation.document_name}</span>
      {locationParts && (
        <span className={styles.chipLocation}>{locationParts}</span>
      )}
    </Link>
  );
}
