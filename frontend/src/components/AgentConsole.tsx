"use client";

import React, { useState, useEffect, useRef } from "react";
import { ChevronDown, ChevronRight, Activity, Cpu, CheckCircle2 } from "lucide-react";
import { useAgentStream, AgentLogEntry } from "@/hooks/useAgentStream";
import styles from "./AgentConsole.module.css";

interface AgentConsoleProps {
  requestId: string | null;
  title?: string;
  defaultExpanded?: boolean;
}

// Map agent names to a distinct color scheme
const getAgentClass = (name: string) => {
  switch (name) {
    case "Ingestion Agent": return styles.agentIngestion;
    case "Graph Agent": return styles.agentGraph;
    case "Compliance Agent": return styles.agentCompliance;
    case "Synthesis Agent": return styles.agentSynthesis;
    default: return styles.agentDefault;
  }
};

export const AgentConsole: React.FC<AgentConsoleProps> = ({
  requestId,
  title = "AI Agent Collaboration Console",
  defaultExpanded = true,
}) => {
  const { logs, isComplete } = useAgentStream(requestId);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom as logs stream in
  useEffect(() => {
    if (expanded && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, expanded]);

  if (!requestId && logs.length === 0) return null;

  return (
    <div className={styles.container}>
      {/* Header (Toggle) */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={styles.headerToggle}
      >
        <div className={styles.headerLeft}>
          <Cpu className={`${styles.headerIcon} ${isComplete ? styles.headerIconDone : styles.headerIconWorking}`} />
          <span className={styles.headerTitle}>{title}</span>
          {!isComplete && (
            <span className={`${styles.statusBadge} ${styles.statusWorking}`}>
              <Activity className={styles.iconSpin} size={12} /> Working...
            </span>
          )}
          {isComplete && (
            <span className={`${styles.statusBadge} ${styles.statusDone}`}>
              <CheckCircle2 size={12} /> Done
            </span>
          )}
        </div>
        <div className={styles.headerRight}>
          <span>{logs.length} steps</span>
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
      </button>

      {/* Expanded Console Logs */}
      {expanded && (
        <div className={styles.consoleBody}>
          {logs.map((log, i) => (
            <LogLine key={i} entry={log} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
};

const LogLine: React.FC<{ entry: AgentLogEntry }> = ({ entry }) => {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = !!entry.detail;

  return (
    <div className={styles.logLineWrap}>
      <div 
        className={`${styles.logEntry} ${hasDetail ? styles.logEntryHoverable : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        <span className={styles.timestamp}>
          [{(entry.timestamp_offset_ms / 1000).toFixed(1)}s]
        </span>
        
        <span className={`${styles.agentBadge} ${getAgentClass(entry.agent_name)}`}>
          {entry.agent_name}
        </span>
        
        <span className={styles.actionSummary}>
          {entry.action_summary}
        </span>

        {entry.metric && (
          <span className={styles.metricBadge}>
            {entry.metric.label}: {entry.metric.value}
          </span>
        )}
      </div>

      {/* Expandable detail row */}
      {expanded && hasDetail && (
        <div className={styles.detailExpand}>
          <pre>{JSON.stringify(entry.detail, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};
