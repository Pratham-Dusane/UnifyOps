"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./interviews.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface InterviewTopic {
  topic: string;
  criticality_score: number;
  documented_depth: "None" | "Thin" | "Medium";
  source_gap: string | null;
}

interface InterviewTurn {
  role: "agent" | "expert";
  content: string;
  timestamp: string;
}

interface InterviewSession {
  session_id: string;
  org_id: string;
  user_uid: string;
  topic: string;
  turns: InterviewTurn[];
  status: "active" | "completed" | "approved";
  transcript: string | null;
  document_id: string | null;
}

export default function InterviewsPage() {
  const { user, profile } = useAuth();
  const router = useRouter();

  // Topics and sessions states
  const [topics, setTopics] = useState<InterviewTopic[]>([]);
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [customTopic, setCustomTopic] = useState("");
  const [responseInput, setResponseInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

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

  const loadTopics = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/interviews/topics`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        setTopics(await res.json());
      }
    } catch {
      // Keep defaults
    }
  }, [getHeaders]);

  useEffect(() => {
    if (user && profile) {
      loadTopics();
    }
  }, [user, profile, loadTopics]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.turns, chatLoading]);

  const handleStartInterview = async (topic: string) => {
    if (!topic.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/interviews/start`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ topic }),
      });
      if (res.ok) {
        setSession(await res.json());
        setCustomTopic("");
      }
    } catch {
      // error state
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitResponse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !responseInput.trim() || chatLoading) return;

    const userInput = responseInput;
    setResponseInput("");
    setChatLoading(true);

    // Optimistically update turns in local state
    const currentTurns = [...session.turns];
    currentTurns.push({
      role: "expert",
      content: userInput,
      timestamp: new Date().toISOString(),
    });
    setSession({ ...session, turns: currentTurns });

    try {
      const res = await fetch(
        `${API_URL}/api/v1/interviews/sessions/${session.session_id}/respond`,
        {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({ response: userInput }),
        }
      );
      if (res.ok) {
        const data = await res.json();
        if (data.status === "active") {
          currentTurns.push({
            role: "agent",
            content: data.next_question,
            timestamp: new Date().toISOString(),
          });
          setSession({ ...session, turns: currentTurns });
        } else if (data.status === "completed") {
          setSession({
            ...session,
            status: "completed",
            turns: currentTurns,
            transcript: data.transcript,
          });
        }
      }
    } catch {
      // error state
    } finally {
      setChatLoading(false);
    }
  };

  const handleApproveTranscript = async () => {
    if (!session) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/interviews/sessions/${session.session_id}/approve`,
        {
          method: "POST",
          headers: getHeaders(),
        }
      );
      if (res.ok) {
        setSession(await res.json());
      }
    } catch {
      // error state
    } finally {
      setLoading(false);
    }
  };

  const handleExit = () => {
    setSession(null);
    loadTopics();
  };

  const getBadgeClass = (score: number) => {
    if (score >= 90) return styles.badgeHigh;
    if (score >= 80) return styles.badgeMed;
    return styles.badgeLow;
  };

  return (
    <div className={styles.container}>
      {/* Sidebar Topics list */}
      <aside className={styles.sidebar} aria-label="Suggested interview topics">
        <h2 className={styles.sidebarTitle}>Retirement Knowledge Extraction Agent</h2>
        <p className={styles.sidebarSubtitle}>Capture unwritten operational judgment before it disappears</p>
        <div className={styles.topicList}>
          {topics.length === 0 ? (
            <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Loading recommended topics...
            </p>
          ) : (
            topics.map((t, idx) => (
              <button
                key={idx}
                className={styles.topicCard}
                onClick={() => handleStartInterview(t.topic)}
                disabled={loading || !!session}
              >
                <span className={styles.topicText}>{t.topic}</span>
                <div className={styles.topicMeta}>
                  <span className={`${styles.badge} ${getBadgeClass(t.criticality_score)}`}>
                    Criticality: {t.criticality_score}%
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>Gaps: {t.documented_depth}</span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Custom topic form */}
        <div className={styles.customTopicForm}>
          <h3 style={{ fontSize: "14px", fontWeight: 600 }}>Custom Interview Topic</h3>
          <input
            type="text"
            className={styles.customInput}
            placeholder="e.g. Mechanical seal replacement P-204"
            value={customTopic}
            onChange={(e) => setCustomTopic(e.target.value)}
            disabled={loading || !!session}
          />
          <button
            className={styles.startBtn}
            onClick={() => handleStartInterview(customTopic)}
            disabled={loading || !customTopic.trim() || !!session}
          >
            Start custom interview
          </button>
        </div>
      </aside>

      {/* Main Interview Area */}
      <main className={styles.main}>
        {!session ? (
          <div className={styles.emptyState}>
            <span className={styles.emptyIcon}></span>
            <h2 className={styles.emptyTitle}>Retirement Knowledge Extraction Agent</h2>
            <p className={styles.emptyText}>
              Capture decades of unwritten operational judgment from senior engineers before retirement.
              This AI-guided interview tool conducts structured technical interviews to preserve
              critical plant knowledge  -  failure patterns, workarounds, and tribal wisdom that
              exists only in experienced minds.
            </p>
            <div className={styles.expertBadge}>
              <span className={styles.expertAvatar}>V</span>
              <div>
                <strong>Vikram Sharma</strong>
                <span>Senior Instrument Engineer · 32 years experience · CDU & VDU specialist</span>
              </div>
            </div>
          </div>
        ) : session.status === "active" ? (
          <>
            <div className={styles.chatHeader}>
              <div>
                <span className={styles.chatTopic}>Topic: {session.topic}</span>
                <span style={{ fontSize: "12px", color: "var(--text-secondary)", marginLeft: "12px" }}>
                  (Question {Math.floor(session.turns.length / 2) + 1} of 4)
                </span>
              </div>
              <button
                onClick={handleExit}
                style={{ fontSize: "13px", color: "var(--status-error)", fontWeight: 500 }}
              >
                Cancel Session
              </button>
            </div>

            <div className={styles.chatArea}>
              {session.turns.map((turn, index) => (
                <div
                  key={index}
                  className={`${styles.bubble} ${turn.role === "agent" ? styles.bubbleAgent : styles.bubbleExpert
                    }`}
                >
                  <span className={turn.role === "agent" ? styles.agentAvatar : styles.vikramAvatar}>
                    {turn.role === "agent" ? "AI" : "V"}
                  </span>
                  <div className={styles.bubbleContent}>
                    <span className={styles.bubbleSender}>
                      {turn.role === "agent" ? "UnifyOps Agent" : "Vikram Sharma"}
                    </span>
                    {turn.content}
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className={styles.typing} aria-label="Agent is thinking">
                  <div className={styles.dot} />
                  <div className={styles.dot} />
                  <div className={styles.dot} />
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <form onSubmit={handleSubmitResponse} className={styles.inputArea}>
              <textarea
                className={styles.textarea}
                placeholder="Type your detailed response here..."
                value={responseInput}
                onChange={(e) => setResponseInput(e.target.value)}
                disabled={chatLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitResponse(e);
                  }
                }}
              />
              <button
                type="submit"
                className={styles.sendBtn}
                disabled={chatLoading || !responseInput.trim()}
              >
                Submit Response
              </button>
            </form>
          </>
        ) : session.status === "completed" ? (
          <>
            <div className={styles.chatHeader}>
              <h2 className={styles.chatTitle}>Review Synthesized Transcript</h2>
              <button
                onClick={handleExit}
                style={{ fontSize: "13px", color: "var(--text-secondary)" }}
              >
                Discard
              </button>
            </div>

            <div className={styles.transcriptArea}>
              <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
                The interview is complete. Review the synthesized Captured Knowledge Document
                below. Once approved, it will be ingested into the knowledge graph, making it
                immediately citable in the Expert Copilot.
              </p>
              <div className={styles.transcriptWrapper}>{session.transcript}</div>
            </div>

            <div className={styles.transcriptActions}>
              <button className={styles.btnApprove} onClick={handleApproveTranscript} disabled={loading}>
                {loading ? "Ingesting..." : "Approve & Ingest into Graph"}
              </button>
            </div>
          </>
        ) : (
          <div className={styles.successPanel}>
            <span className={styles.successIcon}></span>
            <h2 className={styles.successTitle}>Transcript Ingested Successfully!</h2>
            <p className={styles.successText}>
              The captured knowledge transcript has been processed, chunked, and entity-resolved in the
              plant substrate. Other engineers can now retrieve this knowledge cited directly from
              the Copilot.
            </p>
            <div style={{ display: "flex", gap: "16px" }}>
              <button className={styles.btnExplore} onClick={() => router.push("/copilot")}>
                Ask Copilot about this topic
              </button>
              <button
                className={styles.btnExplore}
                style={{ backgroundColor: "var(--bg-elevated)", border: "1px solid var(--border-primary)", color: "var(--text-primary)" }}
                onClick={handleExit}
              >
                Back to dashboard
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
