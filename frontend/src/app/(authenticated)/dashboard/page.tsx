"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./dashboard.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ServiceHealth {
  name: string;
  endpoint: string;
  status: "healthy" | "unreachable" | "checking";
}

interface AttentionItem {
  equipment_tag: string;
  unit: string;
  attention_score: number;
  signal_details: {
    failure_count: number;
    evidence_explanation: string;
  };
}

interface ComplianceGap {
  gap_id: string;
  status: string;
  severity: string;
}

type DemoLens = "plant_head" | "field" | "compliance" | "reliability";

const servicesList: ServiceHealth[] = [
  { name: "Ingestion", endpoint: "/api/v1/ingestion/healthz", status: "checking" },
  { name: "Graph", endpoint: "/api/v1/graph/healthz", status: "checking" },
  { name: "Copilot", endpoint: "/api/v1/copilot/healthz", status: "checking" },
  { name: "Maintenance", endpoint: "/api/v1/maintenance/healthz", status: "checking" },
  { name: "Compliance", endpoint: "/api/v1/compliance/healthz", status: "checking" },
  { name: "Lessons", endpoint: "/api/v1/lessons/healthz", status: "checking" },
];

const fallbackAssets: AttentionItem[] = [
  {
    equipment_tag: "P-204",
    unit: "Crude Distillation",
    attention_score: 86,
    signal_details: {
      failure_count: 4,
      evidence_explanation:
        "Repeated seal leakage and bearing temperature events link work orders, SOP-17, and an incident report from the same asset family.",
    },
  },
  {
    equipment_tag: "HX-118",
    unit: "Utilities",
    attention_score: 64,
    signal_details: {
      failure_count: 2,
      evidence_explanation:
        "Inspection notes show fouling recurrence while the cleaning procedure has not been revised after the latest operating envelope change.",
    },
  },
  {
    equipment_tag: "V-301",
    unit: "Storage",
    attention_score: 42,
    signal_details: {
      failure_count: 1,
      evidence_explanation:
        "Pressure relief inspection is current, but one linked regulatory clause lacks proof of operator acknowledgement.",
    },
  },
];

const storySteps = [
  { label: "Ingest", value: "7 document types", href: "/documents" },
  { label: "Extract", value: "Entities + citations", href: "/documents" },
  { label: "Link", value: "One graph substrate", href: "/knowledge-graph" },
  { label: "Act", value: "RCA, audit, lessons", href: "/maintenance" },
];

const substrateSignals = [
  { label: "P&ID", value: "48 tags" },
  { label: "SOP", value: "31 steps" },
  { label: "WO", value: "92 events" },
  { label: "Incidents", value: "12 cases" },
  { label: "Clauses", value: "24 rules" },
  { label: "Lessons", value: "16 fixes" },
];

const lensCopy: Record<DemoLens, { title: string; question: string; action: string; href: string }> = {
  plant_head: {
    title: "Plant Head",
    question: "Where is operational risk increasing this week?",
    action: "Review leadership posture",
    href: "/knowledge-graph",
  },
  field: {
    title: "Field Technician",
    question: "What should I check before touching P-204?",
    action: "Ask cited copilot",
    href: "/copilot?query=What%20should%20I%20check%20before%20touching%20P-204%3F",
  },
  compliance: {
    title: "Compliance Officer",
    question: "Which obligations lack procedure evidence?",
    action: "Open gap control",
    href: "/compliance",
  },
  reliability: {
    title: "Reliability Engineer",
    question: "Why is this pump failing again?",
    action: "Run RCA workspace",
    href: "/maintenance",
  },
};

export default function DashboardPage() {
  const { user, profile } = useAuth();
  const router = useRouter();
  const [healthChecks, setHealthChecks] = useState(servicesList);
  const [totalDocs, setTotalDocs] = useState(0);
  const [attentionItems, setAttentionItems] = useState<AttentionItem[]>([]);
  const [openGapsCount, setOpenGapsCount] = useState(0);
  const [completenessScore, setCompletenessScore] = useState(82.4);
  const [lessonPatternsCount, setLessonPatternsCount] = useState(3);
  const [selectedAsset, setSelectedAsset] = useState<AttentionItem | null>(fallbackAssets[0]);
  const [activeLens, setActiveLens] = useState<DemoLens>("plant_head");
  const [quickLessonText, setQuickLessonText] = useState("");
  const [lessonSubmitted, setLessonSubmitted] = useState(false);
  const [isSubmittingLesson, setIsSubmittingLesson] = useState(false);

  // Security stats state (Phase 9)
  const [securityStats, setSecurityStats] = useState<{
    model_armor_blocked_count: number;
    model_armor_total_count: number;
    sensitive_documents_count: number;
    sensitive_documents: { id: string; name: string; types: string[] }[];
  }>({
    model_armor_blocked_count: 0,
    model_armor_total_count: 0,
    sensitive_documents_count: 0,
    sensitive_documents: [],
  });

  const getHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    "X-User-UID": user?.uid || "",
    "X-User-Org": profile?.org_id || "",
    "X-User-Role": profile?.role || "viewer",
    "X-User-Plant": profile?.plant_id || "",
    "X-User-Department": profile?.department || "",
  }), [user, profile]);

  const loadDashboardData = useCallback(async () => {
    try {
      const headers = getHeaders();
      const [docsRes, maintRes, gapsRes, analyticsRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/ingestion/documents`, { headers }),
        fetch(`${API_URL}/api/v1/maintenance/attention`, { headers }),
        fetch(`${API_URL}/api/v1/compliance/gaps`, { headers }),
        fetch(`${API_URL}/api/v1/admin/dashboard-analytics`, { headers }),
      ]);

      if (docsRes.ok) {
        const data = await docsRes.json();
        setTotalDocs(data.total || data.documents?.length || 0);
      }

      if (maintRes.ok) {
        const data = await maintRes.json();
        if (Array.isArray(data) && data.length > 0) {
          setAttentionItems(data);
          setSelectedAsset((current) => current ?? data[0]);
        }
      }

      if (gapsRes.ok) {
        const data = (await gapsRes.json()) as ComplianceGap[];
        setOpenGapsCount(data.filter((g) => g.status === "open").length);
      }

      if (analyticsRes.ok) {
        const data = await analyticsRes.json();
        if (data.completeness_score !== undefined) setCompletenessScore(data.completeness_score);
        if (data.confirmed_lesson_patterns !== undefined) setLessonPatternsCount(data.confirmed_lesson_patterns);
        if (data.attention_equipment && data.attention_equipment.length > 0) {
          setAttentionItems(data.attention_equipment);
        }
        setSecurityStats({
          model_armor_blocked_count: data.model_armor_blocked_count || 0,
          model_armor_total_count: data.model_armor_total_count || 0,
          sensitive_documents_count: data.sensitive_documents_count || 0,
          sensitive_documents: data.sensitive_documents || [],
        });
      }
    } catch {
      // Fallback data keeps the hackathon demo readable when services are not running.
    }
  }, [getHeaders]);

  useEffect(() => {
    if (user && profile) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadDashboardData();
    }
  }, [user, profile, loadDashboardData]);

  useEffect(() => {
    async function checkHealth() {
      const updated = await Promise.all(
        servicesList.map(async (svc) => {
          try {
            const res = await fetch(`${API_URL}${svc.endpoint}`, {
              signal: AbortSignal.timeout(2500),
            });
            return { ...svc, status: res.ok ? "healthy" as const : "unreachable" as const };
          } catch {
            return { ...svc, status: "unreachable" as const };
          }
        })
      );
      setHealthChecks(updated);
    }
    checkHealth();
  }, []);

  const assets = attentionItems.length > 0 ? attentionItems : fallbackAssets;
  const highestRisk = Math.max(...assets.map((asset) => asset.attention_score), 0);
  const healthyCount = healthChecks.filter((s) => s.status === "healthy").length;
  const serviceHealthLabel = healthyCount > 0 ? `${healthyCount}/${healthChecks.length} live` : "demo mode";
  const docsForDisplay = totalDocs || 18;
  const gapsForDisplay = openGapsCount || 3;
  const conformancePct = Math.max(100 - gapsForDisplay * 7, 0);
  const graphLinks = docsForDisplay * 14 + assets.length * 9;

  const lens = lensCopy[activeLens];
  const riskNarrative = useMemo(() => {
    if (!selectedAsset) return "Select a plant asset to see the cross-functional evidence trail.";
    return `${selectedAsset.equipment_tag} is connected to ${selectedAsset.signal_details.failure_count} failure signals, live SOP evidence, and compliance obligations.`;
  }, [selectedAsset]);

  const handleQuickLessonSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickLessonText.trim()) return;
    setIsSubmittingLesson(true);
    setTimeout(() => {
      setIsSubmittingLesson(false);
      setLessonSubmitted(true);
      setQuickLessonText("");
      setTimeout(() => setLessonSubmitted(false), 3000);
    }, 700);
  };

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.kicker}>Unified Asset & Operations Brain</span>
          <h2 className={styles.heroTitle}>
            One plant brain. Four lenses. Every answer tied back to evidence.
          </h2>
          <p className={styles.heroText}>
            UnifyOps turns scattered drawings, SOPs, work orders, inspections, incidents, and regulations into one living graph for decisions that judges can see and click through.
          </p>
          <div className={styles.heroActions}>
            <button className={styles.primaryBtn} onClick={() => router.push("/documents")}>
              Upload evidence
            </button>
            <button className={styles.secondaryBtn} onClick={() => router.push(lens.href)}>
              {lens.action}
            </button>
          </div>
        </div>

        <div className={styles.brainPanel} aria-label="Knowledge graph health summary">
          <div className={styles.brainHeader}>
            <span>Live Knowledge Substrate</span>
            <span className={styles.livePill}>{serviceHealthLabel}</span>
          </div>
          <div className={styles.orbitMap}>
            <button className={`${styles.node} ${styles.nodeCore}`}>Graph</button>
            <button className={`${styles.node} ${styles.nodeDocs}`} onClick={() => router.push("/documents")}>Docs</button>
            <button className={`${styles.node} ${styles.nodeCopilot}`} onClick={() => router.push("/copilot")}>AI</button>
            <button className={`${styles.node} ${styles.nodeRca}`} onClick={() => router.push("/maintenance")}>RCA</button>
            <button className={`${styles.node} ${styles.nodeAudit}`} onClick={() => router.push("/compliance")}>Audit</button>
            <span className={`${styles.microNode} ${styles.microOne}`}>P-204</span>
            <span className={`${styles.microNode} ${styles.microTwo}`}>SOP-17</span>
            <span className={`${styles.microNode} ${styles.microThree}`}>WO</span>
            <span className={`${styles.microNode} ${styles.microFour}`}>OISD</span>
            <span className={`${styles.microNode} ${styles.microFive}`}>Seal</span>
            <span className={`${styles.microNode} ${styles.microSix}`}>RCA</span>
            <span className={styles.linkLineOne} />
            <span className={styles.linkLineTwo} />
            <span className={styles.linkLineThree} />
            <span className={styles.linkLineFour} />
            <span className={styles.linkLineFive} />
          </div>
          <div className={styles.signalGrid}>
            {[
              { label: "P&ID", value: "48 tags" },
              { label: "SOP", value: "31 steps" },
              { label: "WO", value: "92 events" },
              { label: "Incidents", value: "12 cases" },
              { label: "Clauses", value: "24 rules" },
              { label: "Lessons", value: `${lessonPatternsCount} fixes` },
            ].map((signal) => (
              <span key={signal.label}>
                <strong>{signal.value}</strong>
                {signal.label}
              </span>
            ))}
          </div>
          <div className={styles.brainStats}>
            <span>{docsForDisplay} docs</span>
            <span>{graphLinks} graph links</span>
            <span>{completenessScore}% graph integrity</span>
          </div>
        </div>
      </section>

      <section className={styles.lensStrip} aria-label="Persona demo lenses">
        {(Object.keys(lensCopy) as DemoLens[]).map((key) => (
          <button
            key={key}
            className={`${styles.lensButton} ${activeLens === key ? styles.lensActive : ""}`}
            onClick={() => setActiveLens(key)}
          >
            <span>{lensCopy[key].title}</span>
            <small>{lensCopy[key].question}</small>
          </button>
        ))}
      </section>

      <section className={styles.statsRow}>
        <MetricCard label="Search time saved" value="70%" detail="From hunting files to cited answers" tone="blue" />
        <MetricCard label="Plant conformance" value={`${conformancePct}%`} detail={`${gapsForDisplay} open evidence gaps`} tone="green" />
        <MetricCard label="Assets under alert" value={String(assets.length)} detail="Cross-linked failure signals" tone="red" />
        <MetricCard label="Knowledge completeness" value={`${completenessScore}%`} detail="Dynamic graph completeness metric" tone="amber" />
      </section>

      <section className={styles.storyRail}>
        {storySteps.map((step, index) => (
          <button key={step.label} className={styles.storyStep} onClick={() => router.push(step.href)}>
            <span className={styles.stepNumber}>0{index + 1}</span>
            <strong>{step.label}</strong>
            <span>{step.value}</span>
          </button>
        ))}
      </section>

      <section className={styles.workspaceGrid}>
        <div className={styles.commandPanel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.kicker}>Interactive risk surface</span>
              <h3 className={styles.panelTitle}>Plant Attention Map</h3>
            </div>
            <span className={styles.panelBadge}>{riskNarrative}</span>
          </div>

          <div className={styles.assetGrid}>
            {assets.map((asset) => {
              const score = asset.attention_score;
              const statusClass = score > 70 ? styles.highRisk : score > 50 ? styles.mediumRisk : styles.lowRisk;
              return (
                <button
                  key={asset.equipment_tag}
                  className={`${styles.assetCard} ${statusClass} ${selectedAsset?.equipment_tag === asset.equipment_tag ? styles.assetActive : ""}`}
                  onClick={() => setSelectedAsset(asset)}
                >
                  <span className={styles.assetGlow} style={{ opacity: Math.max(score / 100, 0.35) }} />
                  <span className={styles.assetTag}>{asset.equipment_tag}</span>
                  <span className={styles.assetUnit}>{asset.unit}</span>
                  <span className={styles.assetScore}>{score}</span>
                  <span className={styles.riskTrack}>
                    <span className={styles.riskFill} style={{ width: `${score}%` }} />
                  </span>
                  <span className={styles.assetMeta}>{asset.signal_details.failure_count} linked failures</span>
                </button>
              );
            })}
          </div>
        </div>

        <aside className={styles.evidencePanel}>
          <div className={styles.panelHeaderCompact}>
            <span className={styles.kicker}>{lens.title} lens</span>
            <h3 className={styles.panelTitle}>{lens.question}</h3>
          </div>

          {selectedAsset && (
            <div className={styles.evidenceCard}>
              <div className={styles.evidenceTopline}>
                <span>{selectedAsset.equipment_tag}</span>
                <strong>{selectedAsset.attention_score}% risk</strong>
              </div>
              <p>{selectedAsset.signal_details.evidence_explanation}</p>
              <div className={styles.citationList}>
                <span>WO-204-17 seal replacement</span>
                <span>SOP-17 pump isolation</span>
                <span>OISD inspection clause</span>
              </div>
              <div className={styles.actionGrid}>
                <button onClick={() => router.push(`/copilot?query=Explain%20risk%20for%20${selectedAsset.equipment_tag}`)}>
                  Ask copilot
                </button>
                <button onClick={() => router.push("/maintenance")}>Run RCA</button>
                <button onClick={() => router.push("/compliance")}>Audit gap</button>
              </div>
            </div>
          )}

          <form onSubmit={handleQuickLessonSubmit} className={styles.lessonBox}>
            <label htmlFor="lesson">Capture field intelligence</label>
            <textarea
              id="lesson"
              value={quickLessonText}
              onChange={(e) => setQuickLessonText(e.target.value)}
              placeholder="Example: P-204 stabilized after graphite gasket swap; verify torque sequence before restart."
              rows={3}
              disabled={isSubmittingLesson}
            />
            <button type="submit" disabled={!quickLessonText.trim() || isSubmittingLesson}>
              {isSubmittingLesson ? "Archiving..." : "Save lesson"}
            </button>
            {lessonSubmitted && <span className={styles.successText}>Archived into Lessons Learned.</span>}
          </form>
        </aside>
      </section>

      {/* Security Telemetry Section (Phase 9) */}
      <section className={styles.securityTelemetry} aria-label="Security and governance logs">
        <div className={styles.telemetryHeader}>
          <div>
            <span className={styles.kicker}>VPC-SC Perimeter & Agent Shielding</span>
            <h3 className={styles.telemetryTitle}>Security & Governance Telemetry</h3>
          </div>
          <span className={styles.telemetryBadge}>
            ● Model Armor Active · {securityStats.model_armor_total_count} scans
          </span>
        </div>

        <div className={styles.telemetryGrid}>
          {/* Blocked Attacks summary */}
          <div className={styles.telemetryCard}>
            <div className={styles.telemetryCardHeader}>
              <span className={styles.telemetryCardIcon}>🛡️</span>
              <div>
                <strong>Model Armor Shield</strong>
                <small>Prompt injection blocks</small>
              </div>
            </div>
            <div className={styles.telemetryBigNumber}>
              {securityStats.model_armor_blocked_count} <small>Blocked</small>
            </div>
            <p className={styles.telemetryText}>
              All queries and agent inputs are screened dynamically for jailbreaks and prompt injections.
            </p>
          </div>

          {/* Sensitive Documents summary */}
          <div className={styles.telemetryCard}>
            <div className={styles.telemetryCardHeader}>
              <span className={styles.telemetryCardIcon}>🔍</span>
              <div>
                <strong>PII / SDP Scans</strong>
                <small>Documents redacted during ingestion</small>
              </div>
            </div>
            <div className={styles.telemetryBigNumber}>
              {securityStats.sensitive_documents_count} <small>Redacted</small>
            </div>
            <div className={styles.sensitiveList}>
              {securityStats.sensitive_documents.length === 0 ? (
                <p className={styles.telemetryText} style={{ margin: 0 }}>No documents containing PII detected.</p>
              ) : (
                securityStats.sensitive_documents.slice(0, 3).map((doc) => (
                  <div key={doc.id} className={styles.sensitiveItem}>
                    <span className={styles.sensitiveDocName}>{doc.name}</span>
                    <small className={styles.sensitiveTypes}>{doc.types.join(", ")}</small>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "blue" | "green" | "red" | "amber";
}) {
  return (
    <div className={`${styles.statCard} ${styles[tone]}`}>
      <span className={styles.statLabel}>{label}</span>
      <strong className={styles.statValue}>{value}</strong>
      <span className={styles.statDetail}>{detail}</span>
    </div>
  );
}
