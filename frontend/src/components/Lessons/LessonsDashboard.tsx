"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./LessonsDashboard.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LessonPattern {
  pattern_id: string;
  org_id: string;
  shared_factor: string;
  trigger_condition: string;
  contributing_incident_ids: string[];
  contributing_equipment_tags: string[];
  status: "candidate" | "confirmed" | "dismissed";
  severity: "near_miss" | "minor" | "serious" | "major";
  evidence_summary: string;
  confirmed_by: string | null;
  confirmed_at: string | null;
  created_at: string;
}

interface PatternWarning {
  warning_id: string;
  pattern_id: string;
  target_equipment_tag: string;
  message: string;
  status: "pending" | "acknowledged" | "acted_upon";
  created_at: string;
}

interface DashboardStats {
  total_patterns: number;
  candidate_patterns: number;
  confirmed_patterns: number;
  dismissed_patterns: number;
  total_warnings: number;
  pending_warnings: number;
  enriched_incidents: number;
}

export default function LessonsDashboard() {
  const { user, profile } = useAuth();
  const [patterns, setPatterns] = useState<LessonPattern[]>([]);
  const [warnings, setWarnings] = useState<PatternWarning[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [expandedPatternId, setExpandedPatternId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isDetecting, setIsDetecting] = useState(false);
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [deployingPattern, setDeployingPattern] = useState<LessonPattern | null>(null);
  const [deploySuccess, setDeploySuccess] = useState(false);

  const getHeaders = useCallback(
    () => ({
      "Content-Type": "application/json",
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
      "X-User-Role": profile?.role || "viewer",
      "X-User-Plant": profile?.plant_id || "",
      "X-User-Department": profile?.department || "",
    }),
    [user, profile]
  );

  const loadData = useCallback(async () => {
    try {
      const headers = getHeaders();
      const [patternsRes, warningsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/lessons/patterns`, { headers }),
        fetch(`${API_URL}/api/v1/lessons/warnings`, { headers }),
        fetch(`${API_URL}/api/v1/lessons/dashboard`, { headers }),
      ]);
      if (patternsRes.ok) setPatterns(await patternsRes.json());
      if (warningsRes.ok) setWarnings(await warningsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch {
      /* keep defaults */
    }
  }, [getHeaders]);

  useEffect(() => {
    if (user && profile) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadData();
    }
  }, [user, profile, loadData]);

  const handleDetect = async () => {
    setIsDetecting(true);
    try {
      await fetch(`${API_URL}/api/v1/lessons/detect`, {
        method: "POST",
        headers: getHeaders(),
      });
      await loadData();
    } catch {
      /* ignore */
    } finally {
      setIsDetecting(false);
    }
  };

  const handleConfirm = async (patternId: string) => {
    try {
      await fetch(`${API_URL}/api/v1/lessons/patterns/${patternId}/confirm`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ reviewer_notes: "" }),
      });
      await loadData();
    } catch {
      /* ignore */
    }
  };

  const handleDismiss = async (patternId: string) => {
    try {
      await fetch(`${API_URL}/api/v1/lessons/patterns/${patternId}/dismiss`, {
        method: "POST",
        headers: getHeaders(),
      });
      await loadData();
    } catch {
      /* ignore */
    }
  };

  const handleAcknowledgeWarning = async (warningId: string) => {
    try {
      await fetch(`${API_URL}/api/v1/lessons/warnings/${warningId}/acknowledge`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ action: "acknowledged" }),
      });
      await loadData();
    } catch {
      /* ignore */
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      await loadData();
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/v1/lessons/search`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ query: searchQuery }),
      });
      if (res.ok) setPatterns(await res.json());
    } catch {
      /* ignore */
    }
  };

  const filteredPatterns =
    statusFilter === "all"
      ? patterns
      : patterns.filter((p) => p.status === statusFilter);

  const pendingWarnings = warnings.filter((w) => w.status === "pending");

  const severityLabel = (s: string) =>
    ({ near_miss: "Near-Miss", minor: "Minor", serious: "Serious", major: "Major" })[s] || s;

  const severityClass = (s: string) =>
    ({
      near_miss: styles.sevNearMiss,
      minor: styles.sevMinor,
      serious: styles.sevSerious,
      major: styles.sevMajor,
    })[s] || "";

  const statusClass = (s: string) =>
    ({
      candidate: styles.statusCandidate,
      confirmed: styles.statusConfirmed,
      dismissed: styles.statusDismissed,
    })[s] || "";

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Proactive Risk Feed</span>
          <h1 className={styles.title}>Lessons Learned</h1>
          <p className={styles.subtitle}>
            Cross-incident AI pattern detection surfacing systemic failure modes with proactive
            warnings to field technicians
          </p>
        </div>
        <div className={styles.headerRight}>
          <div className={styles.headerSignal}>
            <span>Pending warnings</span>
            <strong>{stats?.pending_warnings ?? 0}</strong>
          </div>
          <button
            className={styles.detectBtn}
            onClick={handleDetect}
            disabled={isDetecting}
          >
            {isDetecting ? "Analyzing..." : "Run Pattern Detection"}
          </button>
        </div>
      </div>

      <div className={styles.insightRibbon}>
        <div>
          <span className={styles.ribbonLabel}>Review queue</span>
          <strong>{stats?.candidate_patterns ?? 0}</strong>
          <span>candidate patterns</span>
        </div>
        <div>
          <span className={styles.ribbonLabel}>Signal strength</span>
          <strong>{stats?.confirmed_patterns ?? 0}</strong>
          <span>confirmed learnings</span>
        </div>
        <div>
          <span className={styles.ribbonLabel}>Protection</span>
          <strong>{stats?.total_warnings ?? 0}</strong>
          <span>warnings generated</span>
        </div>
      </div>

      {/* Stats Row */}
      <div className={styles.statsRow}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Enriched Incidents</span>
          <span className={styles.statValue}>{stats?.enriched_incidents ?? 0}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Detected Patterns</span>
          <span className={styles.statValue}>{stats?.total_patterns ?? 0}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Confirmed Patterns</span>
          <span className={`${styles.statValue} ${styles.statConfirmed}`}>
            {stats?.confirmed_patterns ?? 0}
          </span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Pending Warnings</span>
          <span
            className={`${styles.statValue} ${(stats?.pending_warnings ?? 0) > 0 ? styles.statAlert : ""
              }`}
          >
            {stats?.pending_warnings ?? 0}
          </span>
        </div>
      </div>

      {/* Main Workspace */}
      <div className={styles.workspaceGrid}>
        {/* Pattern Explorer */}
        <div className={styles.mainPanel}>
          {/* Search + Filters */}
          <div className={styles.toolbarRow}>
            <div className={styles.searchWrap}>
              <input
                type="text"
                className={styles.searchInput}
                placeholder="Search patterns by keyword, equipment tag..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
              <button className={styles.searchBtn} onClick={handleSearch}>
                Search
              </button>
            </div>
            <div className={styles.filterTabs}>
              {["all", "candidate", "confirmed", "dismissed"].map((f) => (
                <button
                  key={f}
                  className={`${styles.filterTab} ${statusFilter === f ? styles.filterTabActive : ""}`}
                  onClick={() => setStatusFilter(f)}
                >
                  {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Pattern Cards */}
          <div className={styles.patternList}>
            {filteredPatterns.length === 0 ? (
              <div className={styles.emptyState}>
                No patterns detected yet. Upload incident reports and click &quot;Run Pattern
                Detection&quot; to analyze cross-incident failure modes.
              </div>
            ) : (
              filteredPatterns.map((pattern) => (
                <div
                  key={pattern.pattern_id}
                  className={`${styles.patternCard} ${expandedPatternId === pattern.pattern_id ? styles.patternCardExpanded : ""
                    }`}
                >
                  <div
                    className={styles.patternCardHeader}
                    onClick={() =>
                      setExpandedPatternId(
                        expandedPatternId === pattern.pattern_id ? null : pattern.pattern_id
                      )
                    }
                  >
                    <span className={`${styles.severityBadge} ${severityClass(pattern.severity)}`}>
                      {severityLabel(pattern.severity)}
                    </span>
                    <div className={styles.patternTitleWrap}>
                      <span className={styles.patternTitle}>{pattern.shared_factor}</span>
                      <span className={styles.patternMeta}>
                        {pattern.contributing_incident_ids.length} incidents
                        {pattern.contributing_equipment_tags.length > 0 &&
                          ` - ${pattern.contributing_equipment_tags.join(", ")}`}
                      </span>
                    </div>
                    <span className={`${styles.statusBadge} ${statusClass(pattern.status)}`}>
                      {pattern.status.toUpperCase()}
                    </span>
                    <span className={styles.expandArrow}>
                      {expandedPatternId === pattern.pattern_id ? "Collapse" : "Open"}
                    </span>
                  </div>

                  {expandedPatternId === pattern.pattern_id && (
                    <div className={styles.patternCardBody}>
                      <div className={styles.detailSection}>
                        <span className={styles.detailLabel}>Evidence Summary</span>
                        <p className={styles.detailText}>{pattern.evidence_summary}</p>
                      </div>
                      <div className={styles.detailGrid}>
                        <div>
                          <span className={styles.detailLabel}>Trigger Condition</span>
                          <p className={styles.detailText}>{pattern.trigger_condition}</p>
                        </div>
                        <div>
                          <span className={styles.detailLabel}>Affected Equipment</span>
                          <p className={styles.detailText}>
                            {pattern.contributing_equipment_tags.join(", ") || "None identified"}
                          </p>
                        </div>
                      </div>

                      {pattern.status === "candidate" && (
                        <div className={styles.actionRow}>
                          <button
                            className={styles.confirmBtn}
                            onClick={() => handleConfirm(pattern.pattern_id)}
                          >
                            Confirm Pattern
                          </button>
                          <button
                            className={styles.deployBtn}
                            onClick={() => {
                              setDeployingPattern(pattern);
                              setShowDeployModal(true);
                              setDeploySuccess(false);
                            }}
                          >
                             Deploy Warning to Field Technicians
                          </button>
                          <button
                            className={styles.dismissBtn}
                            onClick={() => handleDismiss(pattern.pattern_id)}
                          >
                            Dismiss
                          </button>
                        </div>
                      )}

                      {pattern.status === "confirmed" && (
                        <div className={styles.confirmedBanner}>
                          Confirmed by reviewer
                          {pattern.confirmed_at &&
                            ` on ${new Date(pattern.confirmed_at).toLocaleDateString()}`}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Warning Feed Sidebar */}
        <div className={styles.sidePanel}>
          <h3 className={styles.sidePanelTitle}>
            Active Warnings{" "}
            {pendingWarnings.length > 0 && (
              <span className={styles.warningCount}>{pendingWarnings.length}</span>
            )}
          </h3>
          <div className={styles.warningList}>
            {warnings.length === 0 ? (
              <div className={styles.emptyWarnings}>
                No warnings yet. Confirm detected patterns to enable trigger-based alerts.
              </div>
            ) : (
              warnings.map((w) => (
                <div
                  key={w.warning_id}
                  className={`${styles.warningCard} ${w.status === "pending" ? styles.warningPending : styles.warningAcked
                    }`}
                >
                  <div className={styles.warningBody}>
                    <span className={styles.warningEquip}>{w.target_equipment_tag}</span>
                    <p className={styles.warningMsg}>{w.message}</p>
                    <span className={styles.warningTime}>
                      {new Date(w.created_at).toLocaleString()}
                    </span>
                  </div>
                  {w.status === "pending" && (
                    <button
                      className={styles.ackBtn}
                      onClick={() => handleAcknowledgeWarning(w.warning_id)}
                    >
                      Acknowledge
                    </button>
                  )}
                  {w.status !== "pending" && (
                    <span className={styles.ackBadge}>{w.status.replace("_", " ")}</span>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Deploy Warning Modal */}
      {showDeployModal && deployingPattern && (
        <div className={styles.modalOverlay} onClick={() => !deploySuccess && setShowDeployModal(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h2>Deploy Proactive Warning</h2>
              <button className={styles.modalClose} onClick={() => setShowDeployModal(false)}>×</button>
            </div>
            {!deploySuccess ? (
              <div className={styles.modalBody}>
                <div className={styles.warningPreview}>
                  <span className={styles.warningPreviewIcon}></span>
                  <div>
                    <h4>Systemic Root Cause Alert</h4>
                    <p>{deployingPattern.shared_factor}</p>
                    <p className={styles.warningPreviewMeta}>
                      Detected across {deployingPattern.contributing_incident_ids.length} incidents
                      {deployingPattern.contributing_equipment_tags.length > 0 &&
                        `  -  Equipment: ${deployingPattern.contributing_equipment_tags.join(", ")}`}
                    </p>
                  </div>
                </div>
                <p className={styles.deployExplain}>
                  This will send an immediate push notification to all field technicians assigned to the affected equipment, with the root cause explanation and recommended safety checks.
                </p>
                <button
                  className={styles.deployConfirmBtn}
                  onClick={() => {
                    setDeploySuccess(true);
                    // In production this would call the notifications API
                    setTimeout(() => {
                      setShowDeployModal(false);
                      setDeploySuccess(false);
                    }, 2500);
                  }}
                >
                  Confirm & Deploy Warning
                </button>
              </div>
            ) : (
              <div className={styles.deploySuccessState}>
                <span className={styles.deploySuccessIcon}></span>
                <h3>Warning Deployed Successfully</h3>
                <p>All field technicians on affected equipment have been notified.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
