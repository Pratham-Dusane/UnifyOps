"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./documents.module.css";

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
  uploaded_by: string;
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

interface ExtractedEntity {
  id: string;
  document_id: string;
  entity_type: string;
  value: string;
  confidence: number;
  source_page: number | null;
  needs_review: boolean;
  reviewed: boolean;
  bounding_box: number[] | null;
}

interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  heading_context: string;
  source_page: number | null;
  token_count: number;
}

interface PIDConnection {
  id: string;
  document_id: string;
  source_tag: string;
  target_tag: string;
  connection_type: string;
  confidence: number;
  status: string;
}

interface DocumentDetail {
  document: DocumentRecord;
  entities: ExtractedEntity[];
  chunks: DocumentChunk[];
  connections: PIDConnection[];
}

interface IngestionStats {
  total_documents: number;
  queued: number;
  processing: number;
  completed: number;
  failed: number;
  needs_review: number;
  by_type: Record<string, number>;
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

const DOC_TYPE_LABELS: Record<string, string> = {
  engineering_drawing: "Engineering Drawing",
  work_order: "Work Order",
  safety_procedure: "Safety Procedure",
  inspection_report: "Inspection Report",
  operating_instruction: "Operating Instruction",
  incident_report: "Incident Report",
  regulatory: "Regulatory",
  unknown: "Unclassified",
};

export default function DocumentsPage() {
  const { user, profile } = useAuth();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [stats, setStats] = useState<IngestionStats | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [filterStage, setFilterStage] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Detail Modal State
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docDetail, setDocDetail] = useState<DocumentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"entities" | "chunks" | "connections">("entities");
  const [reviewDocType, setReviewDocType] = useState<string>("");
  const [reviewNotes, setReviewNotes] = useState<string>("");
  const [editingEntityId, setEditingEntityId] = useState<string | null>(null);
  const [editingEntityValue, setEditingEntityValue] = useState<string>("");

  const getHeaders = (): Record<string, string> => ({
    "X-User-UID": user?.uid || "",
    "X-User-Org": profile?.org_id || "",
  });

  const fetchDocuments = useCallback(async () => {
    const hdrs: Record<string, string> = {
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
    };
    try {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (filterStage) params.set("stage", filterStage);
      if (filterType) params.set("doc_type", filterType);

      const res = await fetch(
        `${API_URL}/api/v1/ingestion/documents?${params}`,
        { headers: hdrs }
      );
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch {
      // Backend may be down
    }
  }, [filterStage, filterType, user?.uid, profile?.org_id]);

  const fetchStats = useCallback(async () => {
    const hdrs: Record<string, string> = {
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
    };
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/stats`, { headers: hdrs });
      if (res.ok) {
        setStats(await res.json());
      }
    } catch {
      // Backend may be down
    }
  }, [user?.uid, profile?.org_id]);

  const handleDeleteDoc = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this document and all its layout chunks, entities, and connections? This action cannot be undone.")) return;

    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/documents/${id}`, {
        method: "DELETE",
        headers: {
          "X-User-UID": user?.uid || "",
          "X-User-Org": profile?.org_id || "",
        },
      });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.id !== id));
        if (selectedDocId === id) {
          setSelectedDocId(null);
          setDocDetail(null);
        }
        await fetchStats();
      } else {
        alert("Failed to delete document.");
      }
    } catch {
      alert("Error deleting document.");
    }
  };

  useEffect(() => {
    if (!profile) return;
    // Initial data load using inline async to avoid set-state-in-effect lint.
    // fetchDocuments and fetchStats are still used for manual refreshes.
    let cancelled = false;
    (async () => {
      try {
        const hdrs = {
          "X-User-UID": user?.uid || "",
          "X-User-Org": profile?.org_id || "",
        };
        const [docsRes, statsRes] = await Promise.all([
          fetch(`${API_URL}/api/v1/ingestion/documents?page=1&page_size=50&stage=${filterStage}&doc_type=${filterType}`, { headers: hdrs }),
          fetch(`${API_URL}/api/v1/ingestion/stats`, { headers: hdrs }),
        ]);
        if (cancelled) return;
        if (docsRes.ok) {
          const data = await docsRes.json();
          setDocuments(data.documents || []);
        }
        if (statsRes.ok) {
          setStats(await statsRes.json());
        }
      } catch {
        // Backend may be down
      }
    })();
    return () => { cancelled = true; };
  }, [profile, filterStage, filterType, user?.uid]);

  const fetchDocDetail = async (id: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/documents/${id}`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setDocDetail(data);
        setReviewDocType(data.document.doc_type || "unknown");
      }
    } catch {
      // Backend may be down
    } finally {
      setDetailLoading(false);
    }
  };

  const handleRowClick = (docId: string) => {
    setSelectedDocId(docId);
    fetchDocDetail(docId);
  };

  const closeDetailModal = () => {
    setSelectedDocId(null);
    setDocDetail(null);
    setReviewNotes("");
    setEditingEntityId(null);
  };

  const handleUpload = async (files: FileList | File[]) => {
    if (!files.length || !profile) return;

    setUploading(true);
    const progress: string[] = [];

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
      progress.push(`Uploading ${files[i].name}...`);
    }
    setUploadProgress([...progress]);

    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/upload`, {
        method: "POST",
        headers: getHeaders(),
        body: formData,
      });

      if (res.ok) {
        const results = await res.json();
        setUploadProgress(
          results.map(
            (r: { filename: string; document_id: string }) =>
              `${r.filename} queued (${r.document_id.slice(0, 8)})`
          )
        );
        // Refresh documents and stats
        await fetchDocuments();
        await fetchStats();
      } else {
        const err = await res.json();
        setUploadProgress([`Upload failed: ${err.detail || "Unknown error"}`]);
      }
    } catch {
      setUploadProgress(["Upload failed: Could not connect to backend"]);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress([]), 5000);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files.length) {
      handleUpload(e.dataTransfer.files);
    }
  };

  const submitDocumentReview = async (action: "approve" | "reject" | "edit") => {
    if (!selectedDocId || !profile) return;

    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/documents/${selectedDocId}/review`, {
        method: "POST",
        headers: {
          ...getHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action,
          corrected_doc_type: action === "edit" ? reviewDocType : undefined,
          reviewer_notes: reviewNotes,
        }),
      });

      if (res.ok) {
        // Refresh detail view, stats, list
        await fetchDocDetail(selectedDocId);
        await fetchDocuments();
        await fetchStats();
        setReviewNotes("");
      }
    } catch {
      // Backend error
    }
  };

  const submitEntityReview = async (entityId: string, action: "approve" | "reject" | "edit", correctedValue?: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/entities/${entityId}/review`, {
        method: "POST",
        headers: {
          ...getHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action,
          corrected_entity_value: correctedValue,
        }),
      });

      if (res.ok) {
        // Refresh detail view
        if (selectedDocId) {
          await fetchDocDetail(selectedDocId);
        }
        setEditingEntityId(null);
      }
    } catch {
      // Backend error
    }
  };

  const submitConnectionReview = async (connectionId: string, action: "approve" | "reject") => {
    try {
      const res = await fetch(`${API_URL}/api/v1/ingestion/connections/${connectionId}/review`, {
        method: "POST",
        headers: {
          ...getHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action,
        }),
      });

      if (res.ok) {
        if (selectedDocId) {
          await fetchDocDetail(selectedDocId);
        }
      }
    } catch {
      // Backend error
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (iso: string): string => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className={styles.pageContainer}>
      {/* 1. TOP HEADER */}
      <div className={styles.topHeader}>
        <div className={styles.headerLeft}>
          <h2 className={styles.pageTitle}>Document Intelligence Hub</h2>
          <p className={styles.pageIntro}>
            Ingest, extract entities, and build the plant knowledge graph.
          </p>
        </div>
      </div>

      {/* 2. METRICS ROW */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Total Docs</span>
          <strong className={styles.metricValue}>{stats?.total_documents ?? 0}</strong>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>In Graph</span>
          <strong className={styles.metricValue}>{stats?.completed ?? 0}</strong>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Processing</span>
          <strong className={styles.metricValue}>{stats?.processing ?? 0}</strong>
        </div>
        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Needs Review</span>
          <strong className={styles.metricValue}>{stats?.needs_review ?? 0}</strong>
        </div>
      </div>

      {/* 3. PIPELINE STEPPER */}
      <div className={styles.pipelineCard}>
        <div className={styles.pipelineBar}>
          <div className={`${styles.pipelineStep} ${styles.stepComplete}`}>
            <span className={styles.stepDot}></span>
            1. Upload
          </div>
          <div className={styles.pipelineConnector}></div>
          <div className={`${styles.pipelineStep} ${styles.stepComplete}`}>
            <span className={styles.stepDot}></span>
            2. Layout OCR
          </div>
          <div className={styles.pipelineConnector}></div>
          <div className={`${styles.pipelineStep} ${styles.stepActive}`}>
            <span className={styles.stepDot}></span>
            3. Entity Extraction
          </div>
          <div className={styles.pipelineConnector}></div>
          <div className={styles.pipelineStep}>
            <span className={styles.stepDot}></span>
            4. Knowledge Graph Integration
          </div>
        </div>
      </div>

      {/* 4. INTAKE CONTROLS */}
      <div className={styles.uploadCard}>
        <h3 className={styles.sectionTitle}>Intake Controls</h3>
            
            <div
              className={`${styles.uploadZone} ${dragActive ? styles.uploadZoneActive : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              aria-label="Upload documents"
            >
              <div className={styles.uploadGlow} />
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.csv,.png,.jpg,.jpeg,.tiff,.tif,.zip,.dwg,.dxf"
                className={styles.fileInput}
                onChange={(e) => e.target.files && handleUpload(e.target.files)}
              />
              <div className={styles.uploadIcon}>
                <UploadIcon />
              </div>
              <p className={styles.uploadTitle}>
                {uploading ? "Uploading..." : "Click or Drop files"}
              </p>
              <div className={styles.uploadFormats}>
                <span>PDF</span>
                <span>CAD</span>
                <span>Images</span>
                <span>Office</span>
              </div>
            </div>

            {/* Upload Progress */}
            {uploadProgress.length > 0 && (
              <div className={styles.progressList}>
                {uploadProgress.map((msg, i) => (
                  <div key={i} className={styles.progressItem}>
                    {msg}
                  </div>
                ))}
              </div>
            )}
      </div>

      {/* 5. DOCUMENT REPOSITORY */}
      <div className={styles.tableCard}>
            <div className={styles.filterRow}>
              <h3 className={styles.sectionTitle}>Document Repository</h3>
              <div className={styles.filters}>
                <select
                  value={filterStage}
                  onChange={(e) => setFilterStage(e.target.value)}
                  className={styles.filterSelect}
                  aria-label="Filter by stage"
                >
                  <option value="">All stages</option>
                  {Object.entries(STAGE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className={styles.filterSelect}
                  aria-label="Filter by type"
                >
                  <option value="">All types</option>
                  {Object.entries(DOC_TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Type</th>
                    <th>Stage</th>
                    <th>Size</th>
                    <th>Entities</th>
                    <th>Uploaded</th>
                    <th className={styles.centerHeader}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.length === 0 ? (
                    <tr>
                      <td colSpan={7} className={styles.emptyRow}>
                        No documents yet. Upload files to begin ingestion.
                      </td>
                    </tr>
                  ) : (
                    documents.map((doc) => (
                      <tr
                        key={doc.id}
                        onClick={() => handleRowClick(doc.id)}
                        className={styles.clickableRow}
                      >
                        <td className={styles.filenameCell}>
                          <span className={styles.filename}>
                            {doc.original_filename}
                          </span>
                          {doc.needs_review && (
                            <span className={styles.reviewBadge}>Review</span>
                          )}
                        </td>
                        <td>
                          <span className={styles.typeBadge}>
                            {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                          </span>
                        </td>
                        <td>
                          <span
                            className={`${styles.stageBadge} ${doc.pipeline_stage === "completed"
                                ? styles.stageCompleted
                                : doc.pipeline_stage === "failed"
                                  ? styles.stageFailed
                                  : doc.pipeline_stage === "needs_review"
                                    ? styles.stageReview
                                    : styles.stageProcessing
                              }`}
                          >
                            {STAGE_LABELS[doc.pipeline_stage] || doc.pipeline_stage}
                          </span>
                        </td>
                        <td className={styles.numericCell}>
                          {formatFileSize(doc.file_size)}
                        </td>
                        <td className={styles.numericCell}>
                          {doc.entity_count > 0 ? (
                            <span className={styles.entityChip}>{doc.entity_count}</span>
                          ) : (
                            <span className={styles.entityChipEmpty}>-</span>
                          )}
                        </td>
                        <td className={styles.dateCell}>{formatDate(doc.created_at)}</td>
                        <td className={styles.actionCell} onClick={(e) => e.stopPropagation()}>
                          <button
                            className={styles.deleteBtn}
                            onClick={(e) => handleDeleteDoc(doc.id, e)}
                            title="Delete Document"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

      {/* ─── Detail Modal (FR-1.7.1, FR-1.7.2, FR-1.7.3) ─── */}
      {selectedDocId && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalContent}>
            <div className={styles.modalHeader}>
              <h2 className={styles.modalTitle}>
                {docDetail?.document.original_filename || "Loading detail..."}
              </h2>
              <button className={styles.closeBtn} onClick={closeDetailModal}>
                &times;
              </button>
            </div>

            {detailLoading ? (
              <div className={styles.modalLoader}>
                <div className={styles.spinner} />
                <p>Loading document metadata...</p>
              </div>
            ) : (
              docDetail && (
                <div className={styles.modalGrid}>
                  {/* Left Column: Details & Document Review */}
                  <div className={styles.metaColumn}>
                    <div className={styles.metaCard}>
                      <h4 className={styles.metaCardTitle}>Pipeline Info</h4>
                      <div className={styles.metaRow}>
                        <span className={styles.metaLabel}>Pipeline Stage:</span>
                        <span
                          className={`${styles.stageBadge} ${docDetail.document.pipeline_stage === "completed"
                              ? styles.stageCompleted
                              : docDetail.document.pipeline_stage === "failed"
                                ? styles.stageFailed
                                : docDetail.document.pipeline_stage === "needs_review"
                                  ? styles.stageReview
                                  : styles.stageProcessing
                            }`}
                        >
                          {STAGE_LABELS[docDetail.document.pipeline_stage] ||
                            docDetail.document.pipeline_stage}
                        </span>
                      </div>
                      {docDetail.document.pipeline_error && (
                        <div className={styles.errorAlert}>
                          <strong>Pipeline Error:</strong> {docDetail.document.pipeline_error}
                        </div>
                      )}
                      <div className={styles.metaRow}>
                        <span className={styles.metaLabel}>MIME Type:</span>
                        <span className={styles.metaValue}>{docDetail.document.mime_type}</span>
                      </div>
                      <div className={styles.metaRow}>
                        <span className={styles.metaLabel}>File Size:</span>
                        <span className={styles.metaValue}>
                          {formatFileSize(docDetail.document.file_size)}
                        </span>
                      </div>
                      <div className={styles.metaRow}>
                        <span className={styles.metaLabel}>Plant / Unit:</span>
                        <span className={styles.metaValue}>
                          {docDetail.document.plant_id || "None"} / {docDetail.document.unit || "None"}
                        </span>
                      </div>
                      <div className={styles.metaRow}>
                        <span className={styles.metaLabel}>Total Pages:</span>
                        <span className={styles.metaValue}>
                          {docDetail.document.page_count ?? "N/A"}
                        </span>
                      </div>
                      <div className={styles.metaRow}>
                        <span className={styles.metaLabel}>Confidence:</span>
                        <span className={styles.metaValue}>
                          {docDetail.document.classification_confidence !== null
                            ? `${(docDetail.document.classification_confidence * 100).toFixed(0)}%`
                            : "N/A"}
                        </span>
                      </div>
                    </div>

                    {/* Human In The Loop Section (FR-1.7.3) */}
                    {docDetail.document.needs_review && (
                      <div className={styles.reviewCard}>
                        <h4 className={styles.reviewCardTitle}>Human-in-the-Loop Review</h4>
                        <div className={styles.reviewReason}>
                          <strong>Reason:</strong> {docDetail.document.review_reason || "Requires review"}
                        </div>

                        <div className={styles.formField}>
                          <label className={styles.inputLabel}>Correct Document Type</label>
                          <select
                            value={reviewDocType}
                            onChange={(e) => setReviewDocType(e.target.value)}
                            className={styles.modalSelect}
                          >
                            {Object.entries(DOC_TYPE_LABELS).map(([key, label]) => (
                              <option key={key} value={key}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className={styles.formField}>
                          <label className={styles.inputLabel}>Reviewer Notes</label>
                          <textarea
                            value={reviewNotes}
                            onChange={(e) => setReviewNotes(e.target.value)}
                            placeholder="Add explanation for correction..."
                            className={styles.modalTextarea}
                          />
                        </div>

                        <div className={styles.actionRow}>
                          <button
                            onClick={() => submitDocumentReview("approve")}
                            className={`${styles.actionBtn} ${styles.btnApprove}`}
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => submitDocumentReview("edit")}
                            className={`${styles.actionBtn} ${styles.btnEdit}`}
                          >
                            Apply Correction
                          </button>
                          <button
                            onClick={() => submitDocumentReview("reject")}
                            className={`${styles.actionBtn} ${styles.btnReject}`}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right Column: Tabbed Entities/Chunks view */}
                  <div className={styles.dataColumn}>
                    <div className={styles.tabHeader}>
                      <button
                        className={`${styles.tabBtn} ${activeTab === "entities" ? styles.tabActive : ""}`}
                        onClick={() => setActiveTab("entities")}
                      >
                        Entities ({docDetail.entities.length})
                      </button>
                      <button
                        className={`${styles.tabBtn} ${activeTab === "chunks" ? styles.tabActive : ""}`}
                        onClick={() => setActiveTab("chunks")}
                      >
                        Layout Chunks ({docDetail.chunks.length})
                      </button>
                      {(docDetail.document.doc_type === "engineering_drawing" || (docDetail.connections && docDetail.connections.length > 0)) && (
                        <button
                          className={`${styles.tabBtn} ${activeTab === "connections" ? styles.tabActive : ""}`}
                          onClick={() => setActiveTab("connections")}
                        >
                          Topology Graph ({docDetail.connections?.length || 0})
                        </button>
                      )}
                    </div>

                    <div className={styles.tabContent}>
                      {/* Tab 1: Entities */}
                      {activeTab === "entities" && (
                        <div className={styles.entityList}>
                          {docDetail.entities.length === 0 ? (
                            <p className={styles.emptyText}>No entities extracted from this document.</p>
                          ) : (
                            docDetail.entities.map((ent) => (
                              <div
                                key={ent.id}
                                className={`${styles.entityItem} ${ent.needs_review ? styles.entityWarning : ""
                                  }`}
                              >
                                <div className={styles.entityHeader}>
                                  <span className={styles.entityType}>
                                    {ent.entity_type.replace("_", " ").toUpperCase()}
                                  </span>
                                  <span className={styles.entityConfidence}>
                                    {(ent.confidence * 100).toFixed(0)}% confidence
                                  </span>
                                </div>

                                {editingEntityId === ent.id ? (
                                  <div className={styles.inlineEditField}>
                                    <input
                                      type="text"
                                      value={editingEntityValue}
                                      onChange={(e) => setEditingEntityValue(e.target.value)}
                                      className={styles.inlineInput}
                                    />
                                    <button
                                      onClick={() => submitEntityReview(ent.id, "edit", editingEntityValue)}
                                      className={styles.inlineSaveBtn}
                                    >
                                      Save
                                    </button>
                                    <button
                                      onClick={() => setEditingEntityId(null)}
                                      className={styles.inlineCancelBtn}
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                ) : (
                                  <div className={styles.entityBody}>
                                    <span className={styles.entityValue}>{ent.value}</span>
                                    <div className={styles.entityActions}>
                                      <button
                                        onClick={() => {
                                          setEditingEntityId(ent.id);
                                          setEditingEntityValue(ent.value);
                                        }}
                                        className={styles.entityActionBtn}
                                      >
                                        Edit
                                      </button>
                                      {ent.needs_review && (
                                        <>
                                          <button
                                            onClick={() => submitEntityReview(ent.id, "approve")}
                                            className={`${styles.entityActionBtn} ${styles.btnTextApprove}`}
                                          >
                                            Approve
                                          </button>
                                          <button
                                            onClick={() => submitEntityReview(ent.id, "reject")}
                                            className={`${styles.entityActionBtn} ${styles.btnTextReject}`}
                                          >
                                            Reject
                                          </button>
                                        </>
                                      )}
                                    </div>
                                  </div>
                                )}
                                {ent.needs_review && (
                                  <div className={styles.warningNote}>
                                    Flagged for review
                                  </div>
                                )}
                              </div>
                            ))
                          )}
                        </div>
                      )}

                      {/* Tab 2: Chunks */}
                      {activeTab === "chunks" && (
                        <div className={styles.chunkList}>
                          {docDetail.chunks.length === 0 ? (
                            <p className={styles.emptyText}>No text chunks generated yet.</p>
                          ) : (
                            docDetail.chunks.map((chk) => (
                              <div key={chk.id} className={styles.chunkItem}>
                                <div className={styles.chunkHeader}>
                                  <span className={styles.chunkIndex}>
                                    Chunk #{chk.chunk_index + 1}
                                  </span>
                                  {chk.source_page && (
                                    <span className={styles.chunkPage}>Page {chk.source_page}</span>
                                  )}
                                  <span className={styles.chunkTokens}>
                                    {chk.token_count} tokens
                                  </span>
                                </div>
                                {chk.heading_context && (
                                  <div className={styles.headingContext}>
                                    <strong>Context:</strong> {chk.heading_context}
                                  </div>
                                )}
                                <p className={styles.chunkText}>{chk.text}</p>
                              </div>
                            ))
                          )}
                        </div>
                      )}

                      {/* Tab 3: P&ID Connections */}
                      {activeTab === "connections" && (
                        <div className={styles.entityList}>
                          {!docDetail.connections || docDetail.connections.length === 0 ? (
                            <p className={styles.emptyText}>No candidate drawing connections detected.</p>
                          ) : (
                            docDetail.connections.map((conn) => (
                              <div
                                key={conn.id}
                                className={`${styles.entityItem} ${conn.status === "pending" ? styles.entityWarning : ""
                                  }`}
                              >
                                <div className={styles.entityHeader}>
                                  <span className={styles.entityType}>
                                    {conn.connection_type}
                                  </span>
                                  <span className={styles.entityConfidence}>
                                    {(conn.confidence * 100).toFixed(0)}% confidence
                                  </span>
                                </div>
                                <div className={styles.entityBody}>
                                  <span className={styles.entityValue}>
                                    {conn.source_tag} ──[{conn.connection_type}]──&gt; {conn.target_tag}
                                  </span>
                                  {conn.status === "pending" && (
                                    <div className={styles.entityActions}>
                                      <button
                                        onClick={() => submitConnectionReview(conn.id, "approve")}
                                        className={`${styles.entityActionBtn} ${styles.btnTextApprove}`}
                                      >
                                        Approve
                                      </button>
                                      <button
                                        onClick={() => submitConnectionReview(conn.id, "reject")}
                                        className={`${styles.entityActionBtn} ${styles.btnTextReject}`}
                                      >
                                        Reject
                                      </button>
                                    </div>
                                  )}
                                  {conn.status !== "pending" && (
                                    <span className={styles.warningNote}>
                                      Status: {conn.status.toUpperCase()}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function UploadIcon() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}
