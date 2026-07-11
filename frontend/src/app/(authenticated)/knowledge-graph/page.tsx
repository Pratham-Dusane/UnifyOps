"use client";

import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./knowledge-graph.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Node {
  id: string;
  label: string;
  type: string;
  properties: {
    doc_type?: string;
    status?: string;
    pipeline_stage?: string;
    plant_id?: string;
    unit?: string;
    entity_type?: string;
    confidence?: number;
    canonical_id?: string;
    aliases?: string[];
  };
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface Edge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties?: {
    status?: string;
    confidence?: number;
  };
}

interface GraphData {
  nodes: Node[];
  edges: Edge[];
}

interface SearchResult {
  id: string;
  value: string;
  entity_type: string;
  confidence: number;
}

const TYPE_COLORS: Record<string, string> = {
  Document: "#3b82f6",       // Blue
  EquipmentTag: "#10b981",   // Emerald/Green
  Location: "#8b5cf6",       // Purple
  Person: "#f59e0b",         // Amber
  RegulatoryClause: "#ef4444", // Red
  ProcedureStep: "#ec4899",  // Pink
  FailureMode: "#6366f1",    // Indigo
  Material: "#14b8a6",       // Teal
  Measurement: "#84cc16",    // Lime
};

const EDGE_COLORS: Record<string, string> = {
  CONNECTS_TO: "#10b981",
  PERFORMED_ON: "#8b5cf6",
  INVOLVED_IN: "#f59e0b",
  GOVERNED_BY_SOP: "#ec4899",
  GOVERNED_BY: "#ef4444",
  RESOLVED_TO: "#cbd5e1",
  SUPERSEDES: "#f43f5e",
  HAS_ENTITY: "#94a3b8",
};

// Rounded rectangle helper for canvas rendering
const drawRoundedRect = (ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) => {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
};

export default function KnowledgeGraphPage() {
  const { user, profile } = useAuth();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Data state
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [hops, setHops] = useState(2);
  const [isPanelOpen, setIsPanelOpen] = useState(true);

  // Zoom/pan state
  const transformRef = useRef({ x: 0, y: 0, k: 1 });
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const activeDragNodeRef = useRef<Node | null>(null);
  const hoverNodeRef = useRef<Node | null>(null);

  // Fetch Neighborhood
  const fetchNeighborhood = (nodeId: string, customHops = hops) => {
    if (!profile) return;
    const hdrs = {
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
    };
    (async () => {
    try {
      const res = await fetch(
        `${API_URL}/api/v1/graph/neighborhood?node_id=${encodeURIComponent(nodeId)}&hops=${customHops}`,
        { headers: hdrs }
      );
      if (res.ok) {
        const data: GraphData = await res.json();
        
        // Match existing coordinates if updating
        const coordMap = new Map<string, { x: number; y: number }>();
        graphData.nodes.forEach(n => {
          if (n.x !== undefined && n.y !== undefined) {
            coordMap.set(n.id, { x: n.x, y: n.y });
          }
        });

        const width = canvasRef.current?.width || 800;
        const height = canvasRef.current?.height || 600;

        const newNodes = data.nodes.map(n => {
          const old = coordMap.get(n.id);
          return {
            ...n,
            x: old ? old.x : width / 2 + (Math.random() - 0.5) * 300,
            y: old ? old.y : height / 2 + (Math.random() - 0.5) * 300,
            vx: 0,
            vy: 0,
          };
        });

        setGraphData({ nodes: newNodes, edges: data.edges });
        
        const selectTarget = newNodes.find(n => n.id === nodeId) || newNodes[0] || null;
        setSelectedNode(selectTarget);
      }
    } catch (err) {
      console.error("Failed to load graph neighborhood:", err);
    }
    })();
  };

  useEffect(() => {
    if (!profile) return;
    const hdrs = {
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
    };
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/ingestion/documents?page=1&page_size=1`, { headers: hdrs });
        if (res.ok && !cancelled) {
          const data = await res.json();
          if (data.documents && data.documents.length > 0) {
            fetchNeighborhood(data.documents[0].id);
          }
        }
      } catch {}
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, user?.uid]);

  useEffect(() => {
    if (searchQuery.trim().length < 2 || !profile) {
      setSearchResults([]);
      return;
    }
    const hdrs = {
      "X-User-UID": user?.uid || "",
      "X-User-Org": profile?.org_id || "",
    };
    const delayDebounce = setTimeout(async () => {
      try {
        const res = await fetch(
          `${API_URL}/api/v1/graph/search?q=${encodeURIComponent(searchQuery)}`,
          { headers: hdrs }
        );
        if (res.ok) {
          setSearchResults(await res.json());
        }
      } catch {}
    }, 300);

    return () => clearTimeout(delayDebounce);
  }, [searchQuery, profile, user?.uid]);

  // Force-directed Simulation Loop
  useEffect(() => {
    let animFrameId: number;
    
    const runSimulation = () => {
      const { nodes, edges } = graphData;
      if (nodes.length === 0) return;

      const width = canvasRef.current?.width || 800;
      const height = canvasRef.current?.height || 600;
      const center = { x: width / 2, y: height / 2 };

      // Multi-pass force application
      for (let step = 0; step < 3; step++) {
        // A. Repulsion (Strong anti-gravity layout)
        for (let i = 0; i < nodes.length; i++) {
          const n1 = nodes[i];
          for (let j = i + 1; j < nodes.length; j++) {
            const n2 = nodes[j];
            const dx = n1.x! - n2.x!;
            const dy = n1.y! - n2.y!;
            const distSq = dx * dx + dy * dy + 0.1;
            const dist = Math.sqrt(distSq);
            
            if (dist < 400) {
              const force = 18000 / distSq;
              const fx = (dx / dist) * force;
              const fy = (dy / dist) * force;
              
              n1.vx! += fx;
              n1.vy! += fy;
              n2.vx! -= fx;
              n2.vy! -= fy;
            }

            // Strict Overlap Prevention
            const r1 = n1.type === "Document" || n1.type === "EquipmentTag" ? 18 : 12;
            const r2 = n2.type === "Document" || n2.type === "EquipmentTag" ? 18 : 12;
            const minDist = r1 + r2 + 40; // minimum clear gap between nodes
            if (dist < minDist) {
              const overlap = minDist - dist;
              const fx = (dx / dist) * overlap * 0.5;
              const fy = (dy / dist) * overlap * 0.5;
              n1.x! += fx;
              n1.y! += fy;
              n2.x! -= fx;
              n2.y! -= fy;
            }
          }
        }

        // B. Attraction (Slightly relaxed links)
        const nodeMap = new Map(nodes.map(n => [n.id, n]));
        edges.forEach(edge => {
          const sNode = nodeMap.get(edge.source);
          const tNode = nodeMap.get(edge.target);
          if (sNode && tNode) {
            const dx = tNode.x! - sNode.x!;
            const dy = tNode.y! - sNode.y!;
            const dist = Math.sqrt(dx * dx + dy * dy) || 0.1;
            const targetDist = 180;
            const force = (dist - targetDist) * 0.035;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            sNode.vx! += fx;
            sNode.vy! += fy;
            tNode.vx! -= fx;
            tNode.vy! -= fy;
          }
        });

        // C. Gravity / Centering
        nodes.forEach(node => {
          if (node === activeDragNodeRef.current) return;
          const dx = center.x - node.x!;
          const dy = center.y - node.y!;
          node.vx! += dx * 0.005;
          node.vy! += dy * 0.005;

          // Update position
          node.x! += node.vx!;
          node.y! += node.vy!;

          // Friction damping
          node.vx! *= 0.80;
          node.vy! *= 0.80;
        });
      }

      // Draw
      drawGraph();
      animFrameId = requestAnimationFrame(runSimulation);
    };

    const drawGraph = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const rect = canvas.getBoundingClientRect();
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      ctx.save();
      const t = transformRef.current;
      ctx.translate(t.x, t.y);
      ctx.scale(t.k, t.k);

      // Draw Technical Dotted Background Grid
      ctx.strokeStyle = "rgba(226, 232, 240, 0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash([2, 4]);
      const gridSize = 40;
      const startX = Math.floor((-t.x) / t.k / gridSize) * gridSize - gridSize;
      const endX = Math.floor((canvas.width - t.x) / t.k / gridSize) * gridSize + gridSize;
      const startY = Math.floor((-t.y) / t.k / gridSize) * gridSize - gridSize;
      const endY = Math.floor((canvas.height - t.y) / t.k / gridSize) * gridSize + gridSize;

      for (let x = startX; x <= endX; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, startY);
        ctx.lineTo(x, endY);
        ctx.stroke();
      }
      for (let y = startY; y <= endY; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(startX, y);
        ctx.lineTo(endX, y);
        ctx.stroke();
      }
      ctx.setLineDash([]); // Reset line dash

      // 1. Draw Links
      ctx.lineWidth = 1.5;
      const nodeMap = new Map(graphData.nodes.map(n => [n.id, n]));
      graphData.edges.forEach(edge => {
        const s = nodeMap.get(edge.source);
        const tNode = nodeMap.get(edge.target);
        if (s && tNode) {
          ctx.beginPath();
          ctx.strokeStyle = EDGE_COLORS[edge.type] || "#94a3b8";
          ctx.moveTo(s.x!, s.y!);
          ctx.lineTo(tNode.x!, tNode.y!);
          ctx.stroke();

          // Link labels (Visible ONLY on selection/hover of connected nodes to prevent clutter)
          const isSelectedSource = selectedNode?.id === edge.source || selectedNode?.id === edge.target;
          const isHoveredSource = hoverNodeRef.current?.id === edge.source || hoverNodeRef.current?.id === edge.target;
          
          if (isSelectedSource || isHoveredSource) {
            const mx = (s.x! + tNode.x!) / 2;
            const my = (s.y! + tNode.y!) / 2;
            ctx.font = "bold 9px 'JetBrains Mono', monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            
            const textWidth = ctx.measureText(edge.type).width;
            ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
            ctx.strokeStyle = EDGE_COLORS[edge.type] || "#94a3b8";
            ctx.lineWidth = 1;
            drawRoundedRect(ctx, mx - textWidth / 2 - 4, my - 6, textWidth + 8, 12, 3);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = "#1e293b";
            ctx.fillText(edge.type, mx, my);
          }
        }
      });

      // 2. Draw Nodes
      graphData.nodes.forEach(node => {
        const r = node.type === "Document" || node.type === "EquipmentTag" ? 18 : 12;
        const color = TYPE_COLORS[node.type] || "#94a3b8";

        // Shadows
        ctx.shadowColor = "rgba(0, 0, 0, 0.08)";
        ctx.shadowBlur = 6;
        ctx.shadowOffsetY = 3;

        const isHovered = hoverNodeRef.current?.id === node.id;
        const isSelected = selectedNode?.id === node.id;

        // Outline Ring
        if (isSelected) {
          ctx.beginPath();
          ctx.arc(node.x!, node.y!, r + 6, 0, 2 * Math.PI);
          ctx.strokeStyle = "rgba(59, 130, 246, 0.3)";
          ctx.lineWidth = 4;
          ctx.stroke();
        } else if (isHovered) {
          ctx.beginPath();
          ctx.arc(node.x!, node.y!, r + 4, 0, 2 * Math.PI);
          ctx.strokeStyle = "rgba(148, 163, 184, 0.2)";
          ctx.lineWidth = 3;
          ctx.stroke();
        }

        // Fill Node
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();

        ctx.shadowBlur = 0; // reset shadow
        ctx.shadowOffsetY = 0;

        // White core inside circle
        ctx.beginPath();
        ctx.arc(node.x!, node.y!, r - 4, 0, 2 * Math.PI);
        ctx.fillStyle = "#ffffff";
        ctx.fill();

        // Node Visual Type Letter Code
        ctx.font = "bold 10px 'Inter', sans-serif";
        ctx.fillStyle = color;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const codeChar = node.type.charAt(0);
        ctx.fillText(codeChar, node.x!, node.y!);

        // Node Title label below the node in a technical pill box
        const displayLabel = node.label.length > 20 ? node.label.slice(0, 18) + ".." : node.label;
        ctx.font = "11px 'Inter', sans-serif";
        const labelWidth = ctx.measureText(displayLabel).width;
        const boxWidth = labelWidth + 12;
        const boxHeight = 18;
        const boxX = node.x! - boxWidth / 2;
        const boxY = node.y! + r + 6;

        // Background Box
        ctx.fillStyle = isSelected ? "var(--accent-primary-light)" : "var(--bg-elevated)";
        ctx.strokeStyle = isSelected ? "var(--accent-primary)" : "var(--border-primary)";
        ctx.lineWidth = 1;
        drawRoundedRect(ctx, boxX, boxY, boxWidth, boxHeight, 4);
        ctx.fill();
        ctx.stroke();

        // Text
        ctx.fillStyle = isSelected ? "var(--accent-primary-hover)" : "var(--text-primary)";
        ctx.font = "500 10px 'Inter', sans-serif";
        ctx.fillText(displayLabel, node.x!, boxY + boxHeight / 2);
      });

      ctx.restore();
    };

    animFrameId = requestAnimationFrame(runSimulation);
    return () => cancelAnimationFrame(animFrameId);
  }, [graphData, selectedNode]);

  // Translate screen space to canvas graph coordinate space
  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const t = transformRef.current;
    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;
    return {
      x: (screenX - t.x) / t.k,
      y: (screenY - t.y) / t.k,
    };
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const coords = getCanvasCoords(e);
    // Detect node click
    const clickedNode = graphData.nodes.find(n => {
      const dx = n.x! - coords.x;
      const dy = n.y! - coords.y;
      const r = n.type === "Document" || n.type === "EquipmentTag" ? 18 : 12;
      return dx * dx + dy * dy <= r * r;
    });

    if (clickedNode) {
      activeDragNodeRef.current = clickedNode;
      setSelectedNode(clickedNode);
      // Auto open panel when node is selected
      setIsPanelOpen(true);
    } else {
      dragStartRef.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const coords = getCanvasCoords(e);
    
    if (activeDragNodeRef.current) {
      const node = activeDragNodeRef.current;
      node.x = coords.x;
      node.y = coords.y;
      node.vx = 0;
      node.vy = 0;
      return;
    }

    if (dragStartRef.current) {
      const dx = e.clientX - dragStartRef.current.x;
      const dy = e.clientY - dragStartRef.current.y;
      transformRef.current = {
        ...transformRef.current,
        x: transformRef.current.x + dx,
        y: transformRef.current.y + dy,
      };
      dragStartRef.current = { x: e.clientX, y: e.clientY };
      return;
    }

    const hoverNode = graphData.nodes.find(n => {
      const dx = n.x! - coords.x;
      const dy = n.y! - coords.y;
      const r = n.type === "Document" || n.type === "EquipmentTag" ? 18 : 12;
      return dx * dx + dy * dy <= r * r;
    });
    hoverNodeRef.current = hoverNode || null;
  };

  const handleMouseUp = () => {
    activeDragNodeRef.current = null;
    dragStartRef.current = null;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = 1.1;
    const t = transformRef.current;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const nextK = e.deltaY < 0 ? t.k * zoomFactor : t.k / zoomFactor;
    if (nextK < 0.25 || nextK > 4) return;

    transformRef.current = {
      x: mouseX - (mouseX - t.x) * (nextK / t.k),
      y: mouseY - (mouseY - t.y) * (nextK / t.k),
      k: nextK,
    };
  };

  const resetView = () => {
    transformRef.current = { x: 0, y: 0, k: 1 };
  };

  const getDocumentDetailLink = (node: Node) => {
    if (node.type === "Document") {
      return `/documents?id=${node.id}`;
    }
    const docEdge = graphData.edges.find(e => 
      (e.source === node.id || e.target === node.id) && 
      (e.source.length > 20 || e.target.length > 20)
    );
    if (docEdge) {
      const docId = docEdge.source === node.id ? docEdge.target : docEdge.source;
      return `/documents?id=${docId}`;
    }
    return null;
  };

  return (
    <div className={styles.container}>
      {/* Search Header */}
      <div className={styles.header}>
        <div className={styles.titleArea}>
          <h2 className={styles.title}>Knowledge Graph Explorer</h2>
          <span className={styles.subtitle}>
            Interactive multi-hop map of Equipment, Incidents, Work Orders, and regulations.
          </span>
        </div>

        <div className={styles.controls}>
          <div className={styles.searchWrapper}>
            <input
              type="text"
              placeholder="Search equipment or documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
            />
            {searchResults.length > 0 && (
              <div className={styles.searchResults}>
                {searchResults.map((res) => (
                  <button
                    key={res.id}
                    className={styles.searchResultItem}
                    onClick={() => {
                      fetchNeighborhood(res.id);
                      setSearchQuery("");
                      setSearchResults([]);
                    }}
                  >
                    <span className={styles.neighborLabel}>{res.label}</span>
                    <span className={styles.searchResultType}>{res.type}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          
          <select
            value={hops}
            onChange={(e) => {
              const nextHops = Number(e.target.value);
              setHops(nextHops);
              if (selectedNode) fetchNeighborhood(selectedNode.id, nextHops);
            }}
            className={styles.searchInput}
            style={{ width: "120px" }}
          >
            <option value={1}>1 Hop</option>
            <option value={2}>2 Hops</option>
            <option value={3}>3 Hops</option>
          </select>
        </div>
      </div>

      <div className={styles.mainLayout}>
        {/* Graph Canvas */}
        <div className={styles.canvasContainer}>
          <canvas
            ref={canvasRef}
            className={styles.canvas}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onWheel={handleWheel}
          />
          
          {/* HUD controls (Recenter + Toggle Panel) */}
          <div className={styles.hudButton}>
            <button onClick={resetView} className={styles.hudIcon} title="Recenter View">
              Recenter
            </button>
            <button onClick={() => setIsPanelOpen(!isPanelOpen)} className={styles.hudIcon} title="Toggle Side Panel">
              {isPanelOpen ? "Hide Panel" : "Show Panel"}
            </button>
          </div>

          {/* Color Code Legend */}
          <div className={styles.legend}>
            <span className={styles.legendTitle}>Node Registry</span>
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className={styles.legendItem}>
                <span className={styles.legendColor} style={{ backgroundColor: color }} />
                <span>{type.replace("Tag", "")}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Node Detail Collapsible Side Panel */}
        <div className={`${styles.sidePanel} ${!isPanelOpen ? styles.sidePanelCollapsed : ""}`}>
          {selectedNode ? (
            <>
              <div>
                <h3 className={styles.panelTitle}>
                  {selectedNode.label}
                </h3>
                <span
                  className={styles.panelBadge}
                  style={{
                    backgroundColor: TYPE_COLORS[selectedNode.type] + "25",
                    color: TYPE_COLORS[selectedNode.type],
                  }}
                >
                  {selectedNode.type}
                </span>
              </div>

              {/* Attributes Section */}
              <div className={styles.panelSection}>
                <span className={styles.sectionLabel}>Attributes</span>
                <div className={styles.metaGrid}>
                  {selectedNode.properties.plant_id && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaLabel}>Plant</span>
                      <span className={styles.metaValue}>{selectedNode.properties.plant_id}</span>
                    </div>
                  )}
                  {selectedNode.properties.unit && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaLabel}>Unit Scope</span>
                      <span className={styles.metaValue}>{selectedNode.properties.unit}</span>
                    </div>
                  )}
                  {selectedNode.properties.doc_type && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaLabel}>Doc Class</span>
                      <span className={styles.metaValue}>{selectedNode.properties.doc_type}</span>
                    </div>
                  )}
                  {selectedNode.properties.status && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaLabel}>Status</span>
                      <span className={styles.metaValue}>{selectedNode.properties.status}</span>
                    </div>
                  )}
                  {selectedNode.properties.confidence !== undefined && (
                    <div className={styles.metaItem}>
                      <span className={styles.metaLabel}>AI Confidence</span>
                      <span className={styles.metaValue}>{(selectedNode.properties.confidence * 100).toFixed(0)}%</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Aliases / Alternate terms */}
              {selectedNode.properties.aliases && selectedNode.properties.aliases.length > 0 && (
                <div className={styles.panelSection}>
                  <span className={styles.sectionLabel}>Known Aliases / Tags</span>
                  <div className={styles.aliasList}>
                    {selectedNode.properties.aliases.map((alias, i) => (
                      <span key={i} className={styles.aliasBadge}>{alias}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* One-Hop Neighbors */}
              <div className={styles.panelSection}>
                <span className={styles.sectionLabel}>Linked Relations</span>
                <div className={styles.neighborList}>
                  {graphData.edges
                    .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                    .map(edge => {
                      const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                      const otherNode = graphData.nodes.find(n => n.id === otherId);
                      if (!otherNode) return null;
                      return (
                        <div
                          key={edge.id}
                          className={styles.neighborItem}
                          onClick={() => fetchNeighborhood(otherNode.id)}
                        >
                          <span className={styles.neighborLabel}>{otherNode.label}</span>
                          <span className={styles.neighborType}>
                            {edge.type} ({otherNode.type})
                          </span>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* deep-link to source files (FR-2.4.3) */}
              {getDocumentDetailLink(selectedNode) && (
                <a
                  href={getDocumentDetailLink(selectedNode)!}
                  className={styles.docLinkBtn}
                >
                  View Source Document
                </a>
              )}
            </>
          ) : (
            <div className={styles.emptyState}>
              <p>Select any node to explore its properties and multi-hop relations.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
