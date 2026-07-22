"use client";

import React from "react";
import { FileText } from "lucide-react";
import styles from "./SourceDocumentViewer.module.css";

export interface CitationDocument {
  id: string;
  title: string;
  type: string;
  url: string;
  page?: number | null;
  bbox?: number[] | null;
  char_range?: number[] | null;
}

interface SourceDocumentViewerProps {
  document: CitationDocument;
  highlightedText: string;
}

export const SourceDocumentViewer: React.FC<SourceDocumentViewerProps> = ({ document, highlightedText }) => {
  // If we had a real backend, we'd fetch the document content here.
  // For the prototype/hackathon, we'll simulate the document text containing our highlighted claim.

  if (document.type === "pdf") {
    return (
      <div className={styles.pdfPlaceholder}>
        <FileText className={styles.pdfIcon} size={64} />
        <p className={styles.pdfTitle}>PDF Viewer rendering page {document.page}</p>
        <p className={styles.pdfSubtitle}>
          (Uses react-pdf under the hood. Bounding box overlay for claim: &quot;{highlightedText}&quot;)
        </p>

        {document.bbox && (
          <div className={styles.bboxOverlay}>
            Highlighted Region: [x:{document.bbox[0]}, y:{document.bbox[1]}, w:{document.bbox[2]}, h:{document.bbox[3]}]
          </div>
        )}
      </div>
    );
  }

  // Text fallback rendering
  // We'll simulate a larger document body that embeds our highlighted text
  const simPrefix = `UNIT 4 MAINTENANCE LOG\nID: ${document.id}\nDATE: 2024-10-14\n\nOBSERVATIONS:\nDuring routine inspection of the auxiliary systems, the technician noted elevated temperatures on the primary housing. `;
  const simSuffix = `\n\nACTION TAKEN:\nWork order created for immediate investigation. Production manager notified of potential temporary capacity reduction pending full diagnostics.`;

  return (
    <div className={styles.container}>
      <div className={styles.documentPaper}>
        <h1 className={styles.documentTitle}>{document.title}</h1>
        <pre className={styles.documentContent}>
          {simPrefix}
          <mark className={styles.highlightedClaim} title="Grounded citation claim">
            {highlightedText}
          </mark>
          {simSuffix}
        </pre>
      </div>
    </div>
  );
};
