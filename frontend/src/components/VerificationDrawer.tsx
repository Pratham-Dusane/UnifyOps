"use client";

import React, { useEffect, useState } from "react";
import { X, ExternalLink, ShieldCheck, Info } from "lucide-react";
import { GraphCanvas, GraphPathStep } from "./GraphCanvas";
import { SourceDocumentViewer, CitationDocument } from "./SourceDocumentViewer";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./VerificationDrawer.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface VerificationResponse {
  claim_text: string;
  document: CitationDocument;
  graph_path: GraphPathStep[];
  confidence_score: number;
  grounding_threshold: number;
  reasoning_summary: string;
}

export const VerificationDrawer: React.FC<{ citationId: string; onClose: () => void }> = ({
  citationId,
  onClose,
}) => {
  const { profile } = useAuth();
  const [data, setData] = useState<VerificationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showScorecard, setShowScorecard] = useState(false);

  useEffect(() => {
    // Strip brackets from citation id e.g. "[1]" -> "1"
    const cleanId = citationId.replace(/\[|\]/g, "");
    
    fetch(`${API_URL}/api/v1/copilot/citations/${cleanId}/verification`, {
      headers: {
        "X-User-Org": profile?.org_id || "demo-org",
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error("API failed");
        return res.json();
      })
      .then((json) => {
        if (json && json.document) {
          setData(json);
        } else {
          setData(null);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load verification", err);
        setData(null);
        setLoading(false);
      });
  }, [citationId, profile]);

  return (
    <>
      <div className={styles.overlay} onClick={onClose} />
      
      <div className={styles.drawer}>
        
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.iconWrap}>
              <ShieldCheck size={20} />
            </div>
            <div className={styles.titleGroup}>
              <h2 className={styles.title}>Source Verification</h2>
              <p className={styles.subtitle}>
                Citation {citationId} <span className={styles.badge}>Auditable Trail</span>
              </p>
            </div>
          </div>
          <button onClick={onClose} className={styles.closeBtn}>
            <X size={20} />
          </button>
        </div>

        {data && (
          <div className={styles.claimContext}>
            <span className={styles.claimLabel}>Claim</span>
            <p className={styles.claimText}>"{data.claim_text}"</p>
          </div>
        )}

        <div className={styles.mainContent}>
          {loading ? (
            <div className={styles.loadingState}>
              <div className={styles.spinner} />
              <p>Tracing knowledge graph paths...</p>
            </div>
          ) : data ? (
            <>
              <div className={styles.leftPane}>
                <div className={styles.paneHeader}>Graph Path</div>
                <div className={styles.paneContent}>
                  <GraphCanvas path={data.graph_path} />
                </div>
              </div>

              <div className={styles.rightPane}>
                <div className={styles.paneHeader}>
                  <span>Source Document</span>
                  <span className={styles.documentTitle}>
                    {data.document?.title || "Unknown Document"}
                  </span>
                  <a href={data.document?.url || "#"} target="_blank" rel="noreferrer" className={styles.linkBtn}>
                    <ExternalLink size={14} /> View Original
                  </a>
                </div>
                <div className={styles.paneContent}>
                  <SourceDocumentViewer document={data.document} highlightedText={data.claim_text} />
                </div>
              </div>
            </>
          ) : (
            <div className={styles.errorState}>
              <p>Failed to load verification trace.</p>
            </div>
          )}
        </div>

        {data && (
          <div className={styles.scorecard}>
            <div className={styles.scoreItem}>
              <span className={styles.scoreLabel}>
                Confidence Score
              </span>
              <span className={`${styles.scoreValue} ${data.confidence_score < data.grounding_threshold ? styles.warning : ''}`}>
                {(data.confidence_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className={styles.scoreDetails}>
              <span className={styles.detailsLabel}>Traceability Details</span>
              <p className={styles.detailsText}>{data.reasoning_summary}</p>
            </div>
          </div>
        )}
      </div>
    </>
  );
};
