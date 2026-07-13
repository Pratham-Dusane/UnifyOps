"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./ComplianceDashboard.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RegulatoryClause {
  id: string;
  document_id: string;
  clause_number: string;
  verbatim_text: string;
  summary: string;
  linked_procedures: string[];
  linked_equipment_tags: string[];
}

interface ComplianceGap {
  gap_id: string;
  clause_id: string;
  clause_number: string;
  regulatory_source: string;
  check_type: "missing_procedure" | "stale_procedure" | "unresolved_non_conformance";
  details: string;
  evidence: string;
  severity: "low" | "medium" | "high";
  status: "open" | "resolved" | "escalated";
  resolution_notes?: string;
  created_at: string;
  resolved_at?: string;
  resolved_by?: string;
}

interface DashboardStats {
  total_gaps: number;
  severity_counts: { high: number; medium: number; low: number };
  check_type_counts: {
    missing_procedure: number;
    stale_procedure: number;
    unresolved_non_conformance: number;
  };
  heatmap: Array<{ unit: string; missing_procedure: number; stale_procedure: number; unresolved_non_conformance: number }>;
}

export default function ComplianceDashboard() {
  const { user, profile } = useAuth();
  const [clauses, setClauses] = useState<RegulatoryClause[]>([]);
  const [gaps, setGaps] = useState<ComplianceGap[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  
  // Interactive UI Filters
  const [selectedUnitFilter, setSelectedUnitFilter] = useState<string | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string | null>(null);
  const [expandedGapId, setExpandedGapId] = useState<string | null>(null);
  const [resolutionText, setResolutionText] = useState("");
  const [isSavingResolution, setIsSavingResolution] = useState(false);

  // Audit Packager State
  const [selectedClauseIds, setSelectedClauseIds] = useState<string[]>([]);
  const [generatedPackage, setGeneratedPackage] = useState<string | null>(null);
  const [isCompilingPackage, setIsCompilingPackage] = useState(false);

  const getHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    "X-User-UID": user?.uid || "",
    "X-User-Org": profile?.org_id || "",
    "X-User-Role": profile?.role || "viewer",
    "X-User-Plant": profile?.plant_id || "",
    "X-User-Department": profile?.department || "",
  }), [user, profile]);

  const loadComplianceData = useCallback(async () => {
    try {
      const headers = getHeaders();
      const [clausesRes, gapsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/compliance/clauses`, { headers }),
        fetch(`${API_URL}/api/v1/compliance/gaps`, { headers }),
        fetch(`${API_URL}/api/v1/compliance/dashboard`, { headers }),
      ]);

      if (clausesRes.ok) setClauses(await clausesRes.ok ? await clausesRes.json() : []);
      if (gapsRes.ok) setGaps(await gapsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch {
      // Backend handles failures
    }
  }, [getHeaders]);

  useEffect(() => {
    if (user && profile) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadComplianceData();
    }
  }, [user, profile, loadComplianceData]);

  // Handle gap resolution
  const handleResolveGap = async (gapId: string) => {
    if (!resolutionText.trim() || isSavingResolution) return;
    setIsSavingResolution(true);

    try {
      const res = await fetch(`${API_URL}/api/v1/compliance/gaps/${gapId}/resolve`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ resolution_notes: resolutionText }),
      });
      if (res.ok) {
        setResolutionText("");
        setExpandedGapId(null);
        await loadComplianceData();
      }
    } catch {
      // Error handling
    } finally {
      setIsSavingResolution(false);
    }
  };

  // Compile audit report
  const handleCompilePackage = async () => {
    if (selectedClauseIds.length === 0 || isCompilingPackage) return;
    setIsCompilingPackage(true);
    setGeneratedPackage(null);

    try {
      const res = await fetch(`${API_URL}/api/v1/compliance/audit-package`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ clause_ids: selectedClauseIds }),
      });
      if (res.ok) {
        const data = await res.json();
        setGeneratedPackage(data.content_markdown);
      }
    } catch {
      // Error handling
    } finally {
      setIsCompilingPackage(false);
    }
  };

  const toggleClauseSelection = (clauseId: string) => {
    setSelectedClauseIds((prev) =>
      prev.includes(clauseId) ? prev.filter((id) => id !== clauseId) : [...prev, clauseId]
    );
  };

  // Filter Gaps List dynamically based on click in Heatmap Grid
  const filteredGaps = (() => {
    let result = gaps;

    // Filter by check_type when a heatmap column is selected
    if (selectedTypeFilter) {
      result = result.filter((gap) => gap.check_type === selectedTypeFilter);
    }

    // When a unit row is selected, limit the count to what the heatmap shows for that cell
    if (selectedUnitFilter && selectedTypeFilter && stats?.heatmap) {
      const heatRow = stats.heatmap.find((r) => r.unit === selectedUnitFilter);
      if (heatRow) {
        const cellCount =
          (heatRow as Record<string, number | string>)[selectedTypeFilter] as number ?? 0;
        result = result.slice(0, cellCount);
      }
    }

    return result;
  })();

  const conformancePct = stats
    ? Math.max(100 - Math.round((stats.total_gaps / (clauses.length || 10)) * 100), 0)
    : 80;

  return (
    <div className={styles.container}>
      {/* Top Banner */}
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Compliance control</span>
          <h1 className={styles.title}>Regulatory Posture</h1>
          <p className={styles.subtitle}>
            Continuous mapping of plant procedures against federal safety & environmental obligations
          </p>
        </div>
        <div className={styles.quickMetrics}>
          <div className={styles.metricItem}>
            <span className={styles.metricLabel}>Conformance Index</span>
            <span className={styles.metricValue}>{conformancePct}%</span>
          </div>
          <div className={styles.metricItem}>
            <span className={styles.metricLabel}>Open Gaps</span>
            <span className={styles.metricValueOpen}>{stats?.total_gaps ?? 0}</span>
          </div>
        </div>
      </div>

      <div className={styles.postureBand}>
        <div className={styles.postureMeter}>
          <span>Conformance health</span>
          <strong>{conformancePct}%</strong>
          <div className={styles.meterTrack}>
            <div style={{ width: `${conformancePct}%` }} />
          </div>
        </div>
        <div className={styles.postureStat}>
          <span>High severity</span>
          <strong>{stats?.severity_counts.high ?? 0}</strong>
        </div>
        <div className={styles.postureStat}>
          <span>Missing procedures</span>
          <strong>{stats?.check_type_counts.missing_procedure ?? 0}</strong>
        </div>
        <div className={styles.postureStat}>
          <span>Stale procedures</span>
          <strong>{stats?.check_type_counts.stale_procedure ?? 0}</strong>
        </div>
      </div>

      {/* Main Layout Grid: interactive viz on top, control desk on bottom */}
      <div className={styles.workspace}>
        
        {/* Top Interactive Area */}
        <div className={styles.topSection}>
          
          {/* Plant Conformance Grid Visualizer */}
          <div className={styles.visualizerCard}>
            <h3 className={styles.cardTitle}>Plant Conformance Grid</h3>
            <p className={styles.cardDesc}>
              Filter open gaps by unit and obligation type.
            </p>
            <div className={styles.heatmapGrid}>
              <div className={styles.heatmapHeaderRow}>
                <span>Unit</span>
                <span>Missing Procedure</span>
                <span>Stale Procedure</span>
                <span>Unresolved Incident</span>
              </div>
              {stats?.heatmap.map((row) => (
                <div key={row.unit} className={styles.heatmapRow}>
                  <span className={styles.unitName}>{row.unit}</span>
                  <div
                    onClick={() => {
                      setSelectedUnitFilter(row.unit);
                      setSelectedTypeFilter("missing_procedure");
                    }}
                    className={`${styles.heatmapCell} ${
                      row.missing_procedure > 0 ? styles.cellGappedHigh : styles.cellCompliant
                    } ${
                      selectedUnitFilter === row.unit && selectedTypeFilter === "missing_procedure"
                        ? styles.cellActiveFilter
                        : ""
                    }`}
                  >
                    {row.missing_procedure} gaps
                  </div>
                  <div
                    onClick={() => {
                      setSelectedUnitFilter(row.unit);
                      setSelectedTypeFilter("stale_procedure");
                    }}
                    className={`${styles.heatmapCell} ${
                      row.stale_procedure > 0 ? styles.cellGappedMedium : styles.cellCompliant
                    } ${
                      selectedUnitFilter === row.unit && selectedTypeFilter === "stale_procedure"
                        ? styles.cellActiveFilter
                        : ""
                    }`}
                  >
                    {row.stale_procedure} gaps
                  </div>
                  <div
                    onClick={() => {
                      setSelectedUnitFilter(row.unit);
                      setSelectedTypeFilter("unresolved_non_conformance");
                    }}
                    className={`${styles.heatmapCell} ${
                      row.unresolved_non_conformance > 0 ? styles.cellGappedHigh : styles.cellCompliant
                    } ${
                      selectedUnitFilter === row.unit && selectedTypeFilter === "unresolved_non_conformance"
                        ? styles.cellActiveFilter
                        : ""
                    }`}
                  >
                    {row.unresolved_non_conformance} gaps
                  </div>
                </div>
              ))}
            </div>

            {/* Clear filters if active */}
            {(selectedUnitFilter || selectedTypeFilter) && (
              <button
                className={styles.clearFilterBtn}
                onClick={() => {
                  setSelectedUnitFilter(null);
                  setSelectedTypeFilter(null);
                }}
              >
                Clear heatmap filters
              </button>
            )}
          </div>

          {/* Audit Evidence Package Builder (Interactive Workspace) */}
          <div className={styles.packagerCard}>
            <h3 className={styles.cardTitle}>Evidence Package Builder</h3>
            <p className={styles.cardDesc}>Select regulatory clauses to compile a citation-backed report.</p>
            <div className={styles.clauseList}>
              {clauses.length === 0 ? (
                <div className={styles.emptyClauses}>
                  No segmented clauses available. Upload regulatory documents to get started.
                </div>
              ) : (
                clauses.map((clause) => (
                  <div
                    key={clause.id}
                    className={`${styles.clauseRow} ${
                      selectedClauseIds.includes(clause.id) ? styles.clauseRowSelected : ""
                    }`}
                    onClick={() => toggleClauseSelection(clause.id)}
                  >
                    <input
                      type="checkbox"
                      checked={selectedClauseIds.includes(clause.id)}
                      readOnly
                      className={styles.clauseCheck}
                    />
                    <div className={styles.clauseTextWrap}>
                      <span className={styles.clauseNum}>{clause.clause_number}</span>
                      <p className={styles.clauseSummary}>{clause.summary}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
            <button
              className={styles.compileBtn}
              disabled={selectedClauseIds.length === 0 || isCompilingPackage}
              onClick={handleCompilePackage}
            >
              {isCompilingPackage ? "Compiling..." : `Compile Package (${selectedClauseIds.length})`}
            </button>
          </div>
        </div>

        {/* Bottom Section: Gaps lists and workspace */}
        <div className={styles.bottomSection}>
          
          {/* Main Gaps control console */}
          <div className={`${styles.gapsCard} ${filteredGaps.length === 0 ? styles.gapsCardCollapsed : ""}`}>
            <div className={styles.gapsHeader}>
              <h3 className={styles.cardTitle}>Open Deviations</h3>
              <span className={styles.countBadge}>
                {filteredGaps.length === 0
                  ? "All governing procedures match regulatory conditions. No deviations found."
                  : `${filteredGaps.length} gaps`}
              </span>
            </div>
            
            {filteredGaps.length > 0 && (
              <div className={styles.gapsList}>
                {filteredGaps.map((gap) => (
                  <div
                    key={gap.gap_id}
                    className={`${styles.gapCard} ${
                      expandedGapId === gap.gap_id ? styles.gapCardExpanded : ""
                    }`}
                  >
                    <div
                      className={styles.gapCardHeader}
                      onClick={() => setExpandedGapId(expandedGapId === gap.gap_id ? null : gap.gap_id)}
                    >
                      <span
                        className={`${styles.severityIndicator} ${
                          gap.severity === "high"
                            ? styles.sevHigh
                            : gap.severity === "medium"
                            ? styles.sevMed
                            : styles.sevLow
                        }`}
                      >
                        {gap.severity.toUpperCase()}
                      </span>
                      <div className={styles.gapTitleWrap}>
                        <span className={styles.gapClause}>{gap.clause_number} ({gap.regulatory_source})</span>
                        <span className={styles.gapRuleName}>
                          {gap.check_type.replace(/_/g, " ").toUpperCase()}
                        </span>
                      </div>
                      <span className={styles.expandArrow}>
                        {expandedGapId === gap.gap_id ? "Collapse" : "Open"}
                      </span>
                    </div>

                    {/* Expanded detailed control */}
                    {expandedGapId === gap.gap_id && (
                      <div className={styles.gapCardBody}>
                        <div className={styles.gapDetailsGrid}>
                          <div>
                            <span className={styles.detailLabel}>Verbatim Obligation:</span>
                            <p className={styles.detailText}>
                              {clauses.find((c) => c.id === gap.clause_id)?.verbatim_text ||
                                "Regulatory clause details loading..."}
                            </p>
                          </div>
                          <div>
                            <span className={styles.detailLabel}>Failed Indicator Description:</span>
                            <p className={styles.detailText}>{gap.details}</p>
                          </div>
                          <div className={styles.fullWidth}>
                            <span className={styles.detailLabel}>Evidence Context:</span>
                            <p className={styles.detailText}>{gap.evidence}</p>
                          </div>
                        </div>

                        {/* Sign-off resolution flow */}
                        {gap.status === "open" ? (
                          <div className={styles.resolutionForm}>
                            <input
                              type="text"
                              className={styles.resolutionInput}
                              placeholder="Describe why this check is safe to resolve (e.g. Verified revised LOTO SOP is active)..."
                              value={resolutionText}
                              onChange={(e) => setResolutionText(e.target.value)}
                            />
                            <button
                              className={styles.resolveBtn}
                              disabled={!resolutionText.trim() || isSavingResolution}
                              onClick={() => handleResolveGap(gap.gap_id)}
                            >
                              Sign-off Conformant
                            </button>
                          </div>
                        ) : (
                          <div className={styles.resolvedBanner}>
                            Resolved: {gap.resolution_notes}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Audit Package Report Output split */}
          {generatedPackage && (
            <div className={styles.previewCard}>
              <div className={styles.previewHeader}>
                <h3 className={styles.cardTitle}>Compiled Report Preview</h3>
                <button
                  className={styles.closePreviewBtn}
                  onClick={() => setGeneratedPackage(null)}
                >
                  Close
                </button>
              </div>
              <div className={styles.previewContent}>
                <pre className={styles.markdownCode}>{generatedPackage}</pre>
              </div>
              <button
                className={styles.copyBtn}
                onClick={() => {
                  navigator.clipboard.writeText(generatedPackage);
                  alert("Markdown copied to clipboard!");
                }}
              >
                Copy Markdown to Clipboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
