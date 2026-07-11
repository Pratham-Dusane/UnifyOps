"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./admin.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DocumentRecord {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  doc_type: string;
  classification_confidence: number | null;
  pipeline_stage: string;
  pipeline_error: string | null;
  org_id: string;
  plant_id: string;
  unit: string;
  page_count: number | null;
  entity_count: number;
  chunk_count: number;
  needs_review: boolean;
  review_reason: string | null;
  created_at: string;
  updated_at: string;
}

interface CandidateMerge {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  source_value: string;
  target_value: string;
  similarity: number;
  status: string;
}

interface CompletenessStats {
  score: number;
  linked: number;
  total: number;
  trend: number[];
}

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  uploading: "Uploading",
  uploaded: "Uploaded",
  classifying: "Classifying",
  classified: "Classified",
  extracting_text: "Extracting Text",
  text_extracted: "Text Extracted",
  extracting_entities: "Extracting Entities",
  entities_extracted: "Entities Extracted",
  chunking: "Chunking",
  embedding: "Embedding",
  completed: "Completed",
  failed: "Failed",
  needs_review: "Needs Review",
};

export default function AdminPage() {
  const { user, profile } = useAuth();
  const [activeTab, setActiveTab] = useState<"pipeline" | "merges" | "completeness">("pipeline");

  // Data states
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [candidateMerges, setCandidateMerges] = useState<CandidateMerge[]>([]);
  const [completeness, setCompleteness] = useState<CompletenessStats | null>(null);

  // 1. Fetch Ingestion Documents
  const fetchDocuments = useCallback(async () => {
    if (!profile) return;
    const hdrs = { "X-User-UID": user?.uid || "", "X-User-Org": profile?.org_id || "" };
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/documents?page=1&page_size=50`, { headers: hdrs });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch {}
  }, [profile, user?.uid]);

  // 2. Fetch Proposed Merges
  const fetchCandidateMerges = useCallback(async () => {
    if (!profile) return;
    const hdrs = { "X-User-UID": user?.uid || "", "X-User-Org": profile?.org_id || "" };
    try {
      const res = await fetch(`${API_URL}/api/v1/graph/merges`, { headers: hdrs });
      if (res.ok) {
        setCandidateMerges(await res.json());
      }
    } catch {}
  }, [profile, user?.uid]);

  // 3. Fetch Completeness Metrics
  const fetchCompleteness = useCallback(async () => {
    if (!profile) return;
    const hdrs = { "X-User-UID": user?.uid || "", "X-User-Org": profile?.org_id || "" };
    try {
      const res = await fetch(`${API_URL}/api/v1/graph/completeness`, { headers: hdrs });
      if (res.ok) {
        setCompleteness(await res.json());
      }
    } catch {}
  }, [profile, user?.uid]);

  useEffect(() => {
    if (!profile) return;
    // Initial data load using inline async to avoid set-state-in-effect lint.
    let cancelled = false;
    const hdrs = {
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
    };
    (async () => {
      try {
        const [docsRes, mergesRes, compRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/ingestion/documents?page=1&page_size=50`, { headers: hdrs }),
          fetch(`${API_URL}/api/v1/graph/merges`, { headers: hdrs }),
          fetch(`${API_URL}/api/v1/graph/completeness`, { headers: hdrs }),
        ]);
        if (cancelled) return;
        if (docsRes.ok) {
          const data = await docsRes.json();
          setDocuments(data.documents || []);
        }
        if (mergesRes.ok) setCandidateMerges(await mergesRes.json());
        if (compRes.ok) setCompleteness(await compRes.json());
      } catch {
        // Backend may be down
      }
    })();
    // Setup periodic polling for the pipeline monitor
    const interval = setInterval(fetchDocuments, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [profile, user?.uid, fetchDocuments]);

  // 4. Document Reprocessing trigger
  const handleReprocess = async (docId: string) => {
    const hdrs = { "X-User-UID": user?.uid || "", "X-User-Org": profile?.org_id || "" };
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/documents/${docId}/reprocess`, {
        method: "POST",
        headers: hdrs,
      });
      if (res.ok) {
        fetchDocuments();
      }
    } catch {}
  };

  // 5. Submit candidate merge resolution
  const handleResolveMerge = async (mergeId: string, action: "approve" | "reject") => {
    const hdrs = { "X-User-UID": user?.uid || "", "X-User-Org": profile?.org_id || "" };
    try {
      const res = await fetch(`${API_URL}/api/v1/graph/merges/${mergeId}/resolve`, {
        method: "POST",
        headers: {
          ...hdrs,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        fetchCandidateMerges();
        fetchCompleteness();
      }
    } catch {}
  };

  // Utility badge styling helper
  const getStageClass = (stage: string) => {
    if (stage === "completed") return styles.stageCompleted;
    if (stage === "failed") return styles.stageFailed;
    if (stage === "needs_review") return styles.stageReview;
    if (stage === "queued") return styles.stageQueued;
    return styles.stageProcessing;
  };

  return (
    <div className={styles.container}>
      {/* Page Header */}
      <div className={styles.header}>
        <h2 className={styles.title}>Administration</h2>
        <span className={styles.subtitle}>
          Oversee pipeline queues, resolve AI entity links, and track graph health.
        </span>
      </div>

      {/* Tabs Layout */}
      <div className={styles.tabs}>
        <button
          className={`${styles.tabBtn} ${activeTab === "pipeline" ? styles.tabActive : ""}`}
          onClick={() => setActiveTab("pipeline")}
        >
          Pipeline Monitor ({documents.length})
        </button>
        <button
          className={`${styles.tabBtn} ${activeTab === "merges" ? styles.tabActive : ""}`}
          onClick={() => setActiveTab("merges")}
        >
          Entity Resolution Queue ({candidateMerges.length})
        </button>
        <button
          className={`${styles.tabBtn} ${activeTab === "completeness" ? styles.tabActive : ""}`}
          onClick={() => setActiveTab("completeness")}
        >
          Completeness Dashboard
        </button>
      </div>

      {/* Active Tab View Rendering */}
      {activeTab === "pipeline" && (
        <div>
          {documents.length === 0 ? (
            <div className={styles.emptyState}>No ingestion records found.</div>
          ) : (
            <table className={styles.pipelineTable}>
              <thead>
                <tr>
                  <th className={styles.th}>Filename</th>
                  <th className={styles.th}>Plant / Unit</th>
                  <th className={styles.th}>Status Stage</th>
                  <th className={styles.th}>Entities</th>
                  <th className={styles.th}>Info / Error</th>
                  <th className={styles.th}>Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id} className={styles.tr}>
                    <td className={styles.td}>
                      <div style={{ fontWeight: 500 }}>{doc.original_filename}</div>
                      <div style={{ fontSize: "11px", color: "var(--text-tertiary)" }}>
                        {doc.mime_type} • {(doc.file_size / 1024).toFixed(1)} KB
                      </div>
                    </td>
                    <td className={styles.td}>
                      {doc.plant_id || "—"} / {doc.unit || "—"}
                    </td>
                    <td className={styles.td}>
                      <span className={`${styles.stageBadge} ${getStageClass(doc.pipeline_stage)}`}>
                        {STAGE_LABELS[doc.pipeline_stage] || doc.pipeline_stage}
                      </span>
                    </td>
                    <td className={styles.td}>{doc.entity_count}</td>
                    <td className={styles.td} style={{ maxWidth: "300px" }}>
                      {doc.pipeline_error ? (
                        <span style={{ color: "var(--status-error)", fontSize: "12px" }}>
                          {doc.pipeline_error}
                        </span>
                      ) : doc.review_reason ? (
                        <span style={{ color: "var(--status-warning)", fontSize: "12px" }}>
                          {doc.review_reason}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>Ready</span>
                      )}
                    </td>
                    <td className={styles.td}>
                      <button
                        onClick={() => handleReprocess(doc.id)}
                        className={styles.reprocessBtn}
                        title="Force Pipeline to Rerun OCR and Entity Extraction"
                      >
                        Reprocess
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === "merges" && (
        <div>
          {candidateMerges.length === 0 ? (
            <div className={styles.emptyState}>
              The Entity Resolution queue is empty. All equipment tags resolved deterministically.
            </div>
          ) : (
            <div className={styles.queueGrid}>
              {candidateMerges.map((merge) => (
                <div key={merge.id} className={styles.reviewCard}>
                  <div className={styles.cardHeader}>
                    <div className={styles.cardTitle}>Proposed Equipment Merge</div>
                    <span
                      className={styles.confidenceBadge}
                      style={{
                        backgroundColor: merge.similarity >= 0.85 ? "var(--status-success-light)" : "var(--status-warning-light)",
                        color: merge.similarity >= 0.85 ? "var(--status-success)" : "var(--status-warning)",
                      }}
                    >
                      {(merge.similarity * 100).toFixed(0)}% Match
                    </span>
                  </div>
                  
                  <div className={styles.comparisonBox}>
                    <div className={styles.entityTerm}>
                      <span className={styles.termLabel}>Source Candidate</span>
                      <span className={styles.termValue}>{merge.source_value}</span>
                    </div>
                    <span className={styles.connector}>──⮞</span>
                    <div className={styles.entityTerm}>
                      <span className={styles.termLabel}>Target Canonical</span>
                      <span className={styles.termValue}>{merge.target_value}</span>
                    </div>
                  </div>

                  <div className={styles.actionRow}>
                    <button
                      onClick={() => handleResolveMerge(merge.id, "approve")}
                      className={styles.btnApprove}
                    >
                      Approve Merge
                    </button>
                    <button
                      onClick={() => handleResolveMerge(merge.id, "reject")}
                      className={styles.btnReject}
                    >
                      Keep Separate
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "completeness" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {completeness ? (
            <>
              {/* Completeness score widget */}
              <div className={styles.metricCard}>
                <div className={styles.metricValueArea}>
                  <span className={styles.metricLabel}>Graph Completeness Index</span>
                  <span className={styles.metricValue}>{completeness.score}%</span>
                  <span className={styles.metricSubtext}>
                    Resolved {completeness.linked} out of {completeness.total} extracted equipment nodes.
                  </span>
                </div>

                {/* Trend sparkline bar chart */}
                <div className={styles.trendSparkline}>
                  {completeness.trend.map((val, i) => (
                    <div
                      key={i}
                      className={`${styles.trendBar} ${i === completeness.trend.length - 1 ? styles.trendBarActive : ""}`}
                      style={{ height: `${val}%` }}
                      title={`Historical index score: ${val}%`}
                    />
                  ))}
                </div>
              </div>

              {/* Explanatory notice */}
              <div className={styles.reviewCard}>
                <h4 style={{ fontWeight: 600, fontSize: "0.95rem" }}>Graph completeness insights</h4>
                <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                  This metric measures how tightly coupled your extracted plant assets are. Equipment nodes linked 
                  to Incidents, Safety SOPs, and Work Orders contribute to a higher index. Clean up unlinked nodes by 
                  running Entity Resolution or uploading related manuals.
                </p>
              </div>
            </>
          ) : (
            <div className={styles.emptyState}>Failed to load completeness metrics.</div>
          )}
        </div>
      )}
    </div>
  );
}
