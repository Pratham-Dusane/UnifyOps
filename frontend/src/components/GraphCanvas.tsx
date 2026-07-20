"use client";

import React from "react";
import { Database, FileText, AlertTriangle, Settings, ArrowRight } from "lucide-react";
import styles from "./GraphCanvas.module.css";

export interface GraphPathStep {
  node_id: string;
  node_type: string;
  edge_label: string | null;
  step_order: number;
}

const getNodeIcon = (type: string) => {
  switch (type.toLowerCase()) {
    case "equipment": return <Settings className="w-5 h-5" />;
    case "incident": return <AlertTriangle className="w-5 h-5 text-amber-500" />;
    case "sop": return <FileText className="w-5 h-5 text-blue-500" />;
    default: return <Database className="w-5 h-5 text-slate-500" />;
  }
};

const getNodeColor = (type: string) => {
  switch (type.toLowerCase()) {
    case "equipment": return styles.nodeEquipment;
    case "incident": return styles.nodeIncident;
    case "sop": return styles.nodeSOP;
    default: return styles.nodeDefault;
  }
};

export const GraphCanvas: React.FC<{ path: GraphPathStep[] }> = ({ path }) => {
  if (!path || path.length === 0) {
    return <div className={styles.emptyState}>No graph traversal data available.</div>;
  }

  return (
    <div className={styles.container}>
      {path.map((step, idx) => (
        <React.Fragment key={step.node_id + idx}>
          {/* Edge leading to this node */}
          {step.edge_label && (
            <div className={styles.edgeContainer}>
              <div className={styles.edgeLine}></div>
              <div className={styles.edgeBadge}>
                <ArrowRight size={12} /> {step.edge_label}
              </div>
              <div className={styles.edgeLine}></div>
            </div>
          )}

          {/* Node */}
          <div className={`${styles.nodeCard} ${getNodeColor(step.node_type)}`}>
            {/* Step Number Badge */}
            <div className={styles.nodeStepBadge}>
              {step.step_order + 1}
            </div>
            
            <div className={styles.nodeIconWrap}>
              {getNodeIcon(step.node_type)}
            </div>
            <div className={styles.nodeContent}>
              <span className={styles.nodeType}>
                {step.node_type}
              </span>
              <span className={styles.nodeId}>
                {step.node_id}
              </span>
            </div>
          </div>
        </React.Fragment>
      ))}
    </div>
  );
};
