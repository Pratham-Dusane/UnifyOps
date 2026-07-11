"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./dashboard.module.css";

interface ServiceHealth {
  name: string;
  endpoint: string;
  status: "healthy" | "unreachable" | "checking";
}

const services: ServiceHealth[] = [
  { name: "Ingestion Service", endpoint: "/api/v1/ingestion/healthz", status: "checking" },
  { name: "Graph Service", endpoint: "/api/v1/graph/healthz", status: "checking" },
  { name: "Copilot Service", endpoint: "/api/v1/copilot/healthz", status: "checking" },
  { name: "Maintenance Service", endpoint: "/api/v1/maintenance/healthz", status: "checking" },
  { name: "Compliance Service", endpoint: "/api/v1/compliance/healthz", status: "checking" },
  { name: "Lessons Learned Service", endpoint: "/api/v1/lessons/healthz", status: "checking" },
  { name: "Notification Service", endpoint: "/api/v1/notifications/healthz", status: "checking" },
  { name: "Admin Service", endpoint: "/api/v1/admin/healthz", status: "checking" },
];

export default function DashboardPage() {
  const { profile } = useAuth();
  const [healthChecks, setHealthChecks] = useState(services);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    async function checkHealth() {
      const updated = await Promise.all(
        services.map(async (svc) => {
          try {
            const res = await fetch(`${apiUrl}${svc.endpoint}`, {
              signal: AbortSignal.timeout(3000),
            });
            return {
              ...svc,
              status: res.ok ? ("healthy" as const) : ("unreachable" as const),
            };
          } catch {
            return { ...svc, status: "unreachable" as const };
          }
        })
      );
      setHealthChecks(updated);
    }

    checkHealth();
  }, []);

  const healthyCount = healthChecks.filter((s) => s.status === "healthy").length;
  const totalCount = healthChecks.length;

  return (
    <div className={styles.page}>
      <section className={styles.welcome}>
        <h2 className={styles.welcomeTitle}>
          Welcome{profile?.display_name ? `, ${profile.display_name}` : ""}
        </h2>
        <p className={styles.welcomeSubtitle}>
          AI Industrial Knowledge Intelligence Platform — Unified Asset &amp; Operations Brain
        </p>
        {profile?.org_name && (
          <p className={styles.userGreeting}>
            {profile.org_name} &middot; {profile.role?.replace(/_/g, " ")}
          </p>
        )}
      </section>

      {/* Stats row */}
      <div className={styles.statsRow}>
        <div className={styles.statCard}>
          <span className={styles.statValue}>{healthyCount}/{totalCount}</span>
          <span className={styles.statLabel}>Services Online</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>Phase 0</span>
          <span className={styles.statLabel}>Current Build Phase</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>7</span>
          <span className={styles.statLabel}>Document Types Supported</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>4</span>
          <span className={styles.statLabel}>Intelligence Layers</span>
        </div>
      </div>

      {/* Service health grid */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Service Health</h3>
        <div className={styles.healthGrid}>
          {healthChecks.map((svc) => (
            <div key={svc.name} className={styles.healthCard}>
              <div className={styles.healthHeader}>
                <span
                  className={`${styles.healthDot} ${
                    svc.status === "healthy"
                      ? styles.dotHealthy
                      : svc.status === "checking"
                        ? styles.dotChecking
                        : styles.dotUnreachable
                  }`}
                />
                <span className={styles.healthName}>{svc.name}</span>
              </div>
              <span className={styles.healthStatus}>
                {svc.status === "healthy"
                  ? "Healthy"
                  : svc.status === "checking"
                    ? "Checking..."
                    : "Unreachable"}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Platform modules */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Platform Modules</h3>
        <div className={styles.modulesGrid}>
          {[
            {
              name: "Expert Knowledge Copilot",
              desc: "Ask questions in plain language, get cited answers from your plant's entire documented history.",
              phase: "Phase 3",
              status: "Planned",
            },
            {
              name: "Document Ingestion",
              desc: "Ingest P&IDs, work orders, SOPs, inspection reports, and regulatory documents.",
              phase: "Phase 1",
              status: "Active",
            },
            {
              name: "Knowledge Graph",
              desc: "Unified graph connecting equipment, documents, procedures, and regulatory clauses.",
              phase: "Phase 2",
              status: "Planned",
            },
            {
              name: "Maintenance & RCA",
              desc: "Equipment timelines, predictive attention scores, and AI-assisted root cause analysis.",
              phase: "Phase 4",
              status: "Planned",
            },
            {
              name: "Regulatory Compliance",
              desc: "Clause-level gap detection, audit evidence packages, and compliance trend tracking.",
              phase: "Phase 5",
              status: "Planned",
            },
            {
              name: "Lessons Learned",
              desc: "Cross-incident pattern detection and proactive warning push to operational teams.",
              phase: "Phase 6",
              status: "Planned",
            },
          ].map((mod) => (
            <div key={mod.name} className={styles.moduleCard}>
              <div className={styles.moduleHeader}>
                <h4 className={styles.moduleName}>{mod.name}</h4>
                <span className={styles.moduleBadge}>{mod.phase}</span>
              </div>
              <p className={styles.moduleDesc}>{mod.desc}</p>
              <span className={styles.moduleStatus}>{mod.status}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
