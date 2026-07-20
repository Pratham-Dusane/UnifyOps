"use client";

import React, { useState } from "react";
import { VerificationDrawer } from "./VerificationDrawer";
import styles from "./CitationChip.module.css";

interface CitationChipProps {
  citationId: string;
  sourceDocumentName?: string;
}

export const CitationChip: React.FC<CitationChipProps> = ({ citationId, sourceDocumentName }) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsDrawerOpen(true)}
        className={styles.citationChip}
        title={sourceDocumentName ? `Verify source: ${sourceDocumentName}` : "Verify source"}
      >
        {citationId}
      </button>
      
      {isDrawerOpen && (
        <VerificationDrawer 
          citationId={citationId} 
          onClose={() => setIsDrawerOpen(false)} 
        />
      )}
    </>
  );
};
