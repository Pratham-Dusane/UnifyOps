"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./MaintenanceDashboard.module.css";
import CameraLookup from "./CameraLookup";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Event {
  id: string;
  event_type: "work_order" | "incident" | "inspection" | "sop";
  title: string;
  timestamp: string;
  description: string;
  failure_mode: string | null;
  parts_replaced: string[];
  downtime_hours: number | null;
  document_id: string;
  document_name: string;
}

interface AttentionSignal {
  score: number;
  recurrence_interval_months: number | null;
  months_since_last_service: number;
  failure_count: number;
  severity_incidents_count: number;
  evidence_explanation: string;
}

interface NeedsAttentionItem {
  equipment_id: string;
  equipment_tag: string;
  plant_id: string;
  unit: string;
  attention_score: number;
  signal_details: AttentionSignal;
}

interface RCADraft {
  rca_id: string;
  equipment_tag: string;
  failure_description: string;
  generated_at: string;
  immediate_cause: string;
  five_whys: string[];
  contributing_factors: string;
  corrective_actions: string;
  citations: unknown[];
  status: "draft" | "approved";
  approved_by?: string;
  approved_at?: string;
  reviewer_notes?: string;
}

export default function MaintenanceDashboard() {
  const { user, profile } = useAuth();
  const [activeTab, setActiveTab] = useState<"attention" | "rcas">("attention");
  const [attentionItems, setAttentionItems] = useState<NeedsAttentionItem[]>([]);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<Event[]>([]);
  const [rcaRequestText, setRcaRequestText] = useState("");
  const [activeRca, setActiveRca] = useState<RCADraft | null>(null);
  
  // Historical RCAs state
  const [tagRcas, setTagRcas] = useState<RCADraft[]>([]);
  const [isRcasLoading, setIsRcasLoading] = useState(false);
  const [showRcaInput, setShowRcaInput] = useState(false);
  const [showCameraLookup, setShowCameraLookup] = useState(false);

  const [isTimelineLoading, setIsTimelineLoading] = useState(false);
  const [isRcaGenerating, setIsRcaGenerating] = useState(false);
  const [isRcaSaving, setIsRcaSaving] = useState(false);

  // Edit fields for active RCA
  const [editedImmediateCause, setEditedImmediateCause] = useState("");
  const [editedFiveWhys, setEditedFiveWhys] = useState<string[]>(["", "", "", "", ""]);
  const [editedContributing, setEditedContributing] = useState("");
  const [editedCorrective, setEditedCorrective] = useState("");
  const [reviewerNotes, setReviewerNotes] = useState("");

  const getHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    "X-User-UID": user?.uid || "",
    "X-User-Org": profile?.org_id || "",
    "X-User-Role": profile?.role || "viewer",
    "X-User-Plant": profile?.plant_id || "",
    "X-User-Department": profile?.department || "",
  }), [user, profile]);

  // Load attention signals
  const loadAttentionSignals = useCallback(() => {
    fetch(`${API_URL}/api/v1/maintenance/attention`, {
      headers: getHeaders(),
    })
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setAttentionItems(data);
          if (data.length > 0 && !selectedTag) {
            setSelectedTag(data[0].equipment_tag);
          }
        }
      })
      .catch(() => { });
  }, [getHeaders, selectedTag]);

  // Load RCAs for selected tag
  const loadTagRcas = useCallback(async () => {
    if (!selectedTag) return;
    setIsRcasLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/maintenance/equipment/${selectedTag}/rcas`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        setTagRcas(await res.json());
      }
    } catch {
      // ignore
    } finally {
      setIsRcasLoading(false);
    }
  }, [selectedTag, getHeaders]);

  useEffect(() => {
    if (user && profile) {
      loadAttentionSignals();
    }
  }, [user, profile, loadAttentionSignals]);

  // Load timeline for selected equipment
  const loadTimeline = useCallback(() => {
    if (!selectedTag) return;
    setIsTimelineLoading(true);
    fetch(`${API_URL}/api/v1/maintenance/equipment/${selectedTag}/timeline`, {
      headers: getHeaders(),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.events) {
          setTimeline(data.events);
        }
        setIsTimelineLoading(false);
      })
      .catch(() => {
        setIsTimelineLoading(false);
      });
  }, [selectedTag, getHeaders]);

  useEffect(() => {
    if (user && selectedTag) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadTimeline();
      loadTagRcas();
      setActiveRca(null);
      setShowRcaInput(false);
    }
  }, [user, selectedTag, loadTimeline, loadTagRcas]);

  const handleRunRca = async () => {
    if (!selectedTag || !rcaRequestText.trim() || isRcaGenerating) return;
    setIsRcaGenerating(true);
    setActiveRca(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/maintenance/rca/generate`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          equipment_tag: selectedTag,
          failure_description: rcaRequestText,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as RCADraft;
        setActiveRca(data);
        // Load values into form fields for editing
        setEditedImmediateCause(data.immediate_cause);
        setEditedFiveWhys(data.five_whys);
        setEditedContributing(data.contributing_factors);
        setEditedCorrective(data.corrective_actions);
        setReviewerNotes("");
        setRcaRequestText("");
        setShowRcaInput(false);
        await loadTagRcas();
      }
    } catch {
      // Handle error
    } finally {
      setIsRcaGenerating(false);
    }
  };

  const handleApproveRca = async () => {
    if (!activeRca || isRcaSaving) return;
    setIsRcaSaving(true);

    try {
      const res = await fetch(`${API_URL}/api/v1/maintenance/rca/${activeRca.rca_id}/approve`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          immediate_cause: editedImmediateCause,
          five_whys: editedFiveWhys,
          contributing_factors: editedContributing,
          corrective_actions: editedCorrective,
          reviewer_notes: reviewerNotes,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setActiveRca(data);
        // Reload list of signals (might update counts)
        loadAttentionSignals();
        await loadTagRcas();
      }
    } catch {
      // Handle error
    } finally {
      setIsRcaSaving(false);
    }
  };

  const handleFiveWhysChange = (index: number, val: string) => {
    const updated = [...editedFiveWhys];
    updated[index] = val;
    setEditedFiveWhys(updated);
  };

  const handleSelectRca = (rca: RCADraft) => {
    setActiveRca(rca);
    setEditedImmediateCause(rca.immediate_cause);
    setEditedFiveWhys(rca.five_whys);
    setEditedContributing(rca.contributing_factors);
    setEditedCorrective(rca.corrective_actions);
    setReviewerNotes(rca.reviewer_notes || "");
  };

  return (
    <div className={styles.container}>
      {/* Top Banner */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Maintenance Intelligence & Advisor</h1>
          <p className={styles.subtitle}>
            Diagnose failure recurrence patterns and draft cited Root Cause Analyses
          </p>
        </div>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <button
            className={styles.tabBtn}
            onClick={() => setShowCameraLookup(true)}
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <span>📷</span> Scan Tag Plate
          </button>
          <div className={styles.tabs}>
            <button
              className={`${styles.tabBtn} ${activeTab === "attention" ? styles.activeTab : ""}`}
              onClick={() => setActiveTab("attention")}
            >
              Attention Signals
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className={styles.grid}>
        {/* Left Side: Equipment Attention List */}
        <div className={styles.leftColumn}>
          <div className={styles.panelTitle}>Needs Attention Checklist</div>
          <div className={styles.attentionList}>
            {attentionItems.length === 0 ? (
              <div className={styles.emptySignal}>
                No equipment is flagged for attention yet. Ingest work orders with
                overlapping failure tags to calculate signals.
              </div>
            ) : (
              attentionItems.map((item) => {
                const score = item.attention_score;
                const scoreClass =
                  score > 70
                    ? styles.scoreHigh
                    : score > 40
                      ? styles.scoreMedium
                      : styles.scoreLow;

                return (
                  <div
                    key={item.equipment_tag}
                    className={`${styles.attentionCard} ${selectedTag === item.equipment_tag ? styles.selectedCard : ""
                      }`}
                    onClick={() => {
                      setSelectedTag(item.equipment_tag);
                    }}
                  >
                    <div className={styles.cardHeader}>
                      <span className={styles.equipmentTag}>{item.equipment_tag}</span>
                      <span className={`${styles.scoreBadge} ${scoreClass}`}>
                        {score}% Risk
                      </span>
                    </div>
                    <div className={styles.cardMeta}>
                      Unit: {item.unit} · failures: {item.signal_details.failure_count}
                    </div>
                    <p className={styles.evidenceText}>
                      {item.signal_details.evidence_explanation}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Side: Timeline & RCA draft Workspace */}
        <div className={styles.rightColumn}>
          {selectedTag ? (
            <div className={styles.workspace}>
              {/* Equipment Header */}
              <div className={styles.workspaceHeader}>
                <h2 className={styles.workspaceTitle}>Workspace for {selectedTag}</h2>
                <div className={styles.workspaceMeta}>
                  Timeline history of failures & service logs
                </div>
              </div>

              {/* Timeline segment */}
              <div className={styles.sectionCard}>
                <h3 className={styles.sectionTitle}>Asset History Timeline</h3>
                {isTimelineLoading ? (
                  <div className={styles.loaderWrap}>
                    <div className={styles.spinner} />
                  </div>
                ) : timeline.length === 0 ? (
                  <div className={styles.emptyTimeline}>
                    No maintenance records found for this equipment tag.
                  </div>
                ) : (
                  <div className={styles.timelineContainer}>
                    {timeline.map((ev) => (
                      <div key={ev.id} className={styles.timelineItem}>
                        <div className={styles.timelineIconWrap}>
                          <span
                            className={`${styles.timelineBadge} ${ev.event_type === "incident"
                                ? styles.badgeIncident
                                : ev.event_type === "work_order"
                                  ? styles.badgeWorkOrder
                                  : styles.badgeSop
                              }`}
                          />
                        </div>
                        <div className={styles.timelineContent}>
                          <div className={styles.timelineHeader}>
                            <span className={styles.eventTitle}>{ev.title}</span>
                            <span className={styles.eventTime}>
                              {new Date(ev.timestamp).toLocaleDateString()}
                            </span>
                          </div>
                          <p className={styles.eventDesc}>{ev.description}</p>
                          {(ev.failure_mode || ev.downtime_hours || ev.parts_replaced.length > 0) && (
                            <div className={styles.timelineEnrichment}>
                              {ev.failure_mode && (
                                <span className={styles.enrichTag}>
                                  Mode: {ev.failure_mode}
                                </span>
                              )}
                              {ev.downtime_hours !== null && (
                                <span className={styles.enrichTag}>
                                  Downtime: {ev.downtime_hours} hrs
                                </span>
                              )}
                              {ev.parts_replaced.map((p) => (
                                <span key={p} className={styles.partsTag}>
                                  {p}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* RCA Workspace */}
              <div className={styles.sectionCard}>
                <div className={styles.rcaTitleRow}>
                  <h3 className={styles.sectionTitle}>Root Cause Analysis Agent</h3>
                  {!activeRca && !showRcaInput && (
                    <button
                      className={styles.newRcaBtn}
                      onClick={() => setShowRcaInput(true)}
                    >
                      + Generate New RCA
                    </button>
                  )}
                </div>

                {/* Case 1: Display failure prompt input form */}
                {!activeRca && showRcaInput && (
                  <div className={styles.rcaRequestBox}>
                    <button
                      className={styles.backBtn}
                      onClick={() => setShowRcaInput(false)}
                    >
                      ← Back to RCA Records
                    </button>
                    <textarea
                      className={styles.rcaInput}
                      value={rcaRequestText}
                      onChange={(e) => setRcaRequestText(e.target.value)}
                      placeholder="Describe the failure symptom (e.g. Pump tripped on high bearing temperature and coupling misalignment)..."
                      rows={3}
                      disabled={isRcaGenerating}
                    />
                    <button
                      className={styles.rcaSubmitBtn}
                      onClick={handleRunRca}
                      disabled={!rcaRequestText.trim() || isRcaGenerating}
                    >
                      {isRcaGenerating ? (
                        <>
                          <div className={styles.inlineSpinner} /> Drafting RCA...
                        </>
                      ) : (
                        "Generate RCA Report Draft"
                      )}
                    </button>
                  </div>
                )}

                {/* Case 2: Display list of existing drafts/approvals */}
                {!activeRca && !showRcaInput && (
                  <div className={styles.rcaRecordsList}>
                    {isRcasLoading ? (
                      <div className={styles.loaderWrap}>
                        <div className={styles.spinner} />
                      </div>
                    ) : tagRcas.length === 0 ? (
                      <div className={styles.emptyRcaRecords}>
                        No RCA drafts have been compiled for {selectedTag} yet. Click <b>&quot;Generate New RCA&quot;</b> above to run the AI assistant.
                      </div>
                    ) : (
                      <div className={styles.rcaGrid}>
                        {tagRcas.map((rca) => (
                          <div
                            key={rca.rca_id}
                            className={styles.rcaRecordCard}
                            onClick={() => handleSelectRca(rca)}
                          >
                            <div className={styles.rcaRecordHeader}>
                              <span className={styles.rcaRecordTitle}>
                                {rca.failure_description}
                              </span>
                              <span
                                className={`${styles.rcaRecordStatus} ${
                                  rca.status === "approved" ? styles.statusApproved : styles.statusDraft
                                }`}
                              >
                                {rca.status.toUpperCase()}
                              </span>
                            </div>
                            <div className={styles.rcaRecordMeta}>
                              Created: {new Date(rca.generated_at).toLocaleDateString()}
                              {rca.approved_at && ` · Approved: ${new Date(rca.approved_at).toLocaleDateString()}`}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Case 3: Active RCA Draft Workspace */}
                {activeRca && (
                  <div className={styles.rcaWorkspace}>
                    <button
                      className={styles.backBtn}
                      onClick={() => setActiveRca(null)}
                    >
                      ← Back to RCA Records
                    </button>

                    <div className={styles.warningBanner}>
                      AI-assisted draft — requires engineer review and sign-off
                    </div>

                    <div className={styles.rcaForm}>
                      {/* Immediate Cause */}
                      <div className={styles.formField}>
                        <label className={styles.formLabel}>Immediate Cause</label>
                        <input
                          type="text"
                          className={styles.formInput}
                          value={editedImmediateCause}
                          onChange={(e) => setEditedImmediateCause(e.target.value)}
                          disabled={activeRca.status === "approved"}
                        />
                      </div>

                      {/* 5 Whys */}
                      <div className={styles.formField}>
                        <label className={styles.formLabel}>5-Whys Logical Analysis</label>
                        <div className={styles.fiveWhysInputs}>
                          {editedFiveWhys.map((why, index) => (
                            <div key={index} className={styles.whyRow}>
                              <span className={styles.whyNumber}>Why {index + 1}:</span>
                              <input
                                type="text"
                                className={styles.whyInput}
                                value={why}
                                onChange={(e) => handleFiveWhysChange(index, e.target.value)}
                                disabled={activeRca.status === "approved"}
                              />
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Contributing Factors */}
                      <div className={styles.formField}>
                        <label className={styles.formLabel}>Contributing Factors (Human/Process/Assets)</label>
                        <textarea
                          className={styles.formTextarea}
                          value={editedContributing}
                          onChange={(e) => setEditedContributing(e.target.value)}
                          rows={4}
                          disabled={activeRca.status === "approved"}
                        />
                      </div>

                      {/* Corrective Actions */}
                      <div className={styles.formField}>
                        <label className={styles.formLabel}>Recommended Corrective Actions</label>
                        <textarea
                          className={styles.formTextarea}
                          value={editedCorrective}
                          onChange={(e) => setEditedCorrective(e.target.value)}
                          rows={4}
                          disabled={activeRca.status === "approved"}
                        />
                      </div>

                      {/* Reviewer Notes & Save */}
                      {activeRca.status === "draft" ? (
                        <div className={styles.approvalSection}>
                          <div className={styles.formField}>
                            <label className={styles.formLabel}>Reviewer Sign-off Notes</label>
                            <input
                              type="text"
                              className={styles.formInput}
                              value={reviewerNotes}
                              onChange={(e) => setReviewerNotes(e.target.value)}
                              placeholder="e.g. Verified with LOTO log files, details approved."
                            />
                          </div>
                          <button
                            className={styles.approveBtn}
                            onClick={handleApproveRca}
                            disabled={isRcaSaving}
                          >
                            {isRcaSaving ? "Saving approval..." : "Sign-off & Lock RCA"}
                          </button>
                        </div>
                      ) : (
                        <div className={styles.approvedSection}>
                          <div className={styles.approvedTick}>✓ RCA Approved & Sealed</div>
                          <div className={styles.approvedMeta}>
                            Signed off at {new Date(activeRca.approved_at!).toLocaleString()}
                          </div>
                          {activeRca.reviewer_notes && (
                            <p className={styles.approvedNotes}>
                              Notes: {activeRca.reviewer_notes}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className={styles.emptyWorkspace}>
              Select an asset on the left to review its maintenance history and generate RCAs
            </div>
          )}
        </div>
      </div>
      {showCameraLookup && (
        <CameraLookup
          onClose={() => setShowCameraLookup(false)}
          onMatch={(tag) => setSelectedTag(tag)}
          headers={getHeaders()}
        />
      )}
    </div>
  );
}
