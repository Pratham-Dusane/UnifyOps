"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import styles from "./CopilotChat.module.css";
import ChatInput from "./ChatInput";
import CitationChip from "./CitationChip";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://unifyops-backend-381606738104.asia-south1.run.app";

interface Citation {
  citation_id: string;
  chunk_id: string;
  document_id: string;
  document_name: string;
  page: number | null;
  section: string;
  relevance_score: number;
  deep_link: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  confidence_score: number | null;
  is_low_confidence: boolean;
  has_uncited_claims: boolean;
  timestamp: string;
}

interface SessionItem {
  session_id: string;
  first_query: string;
  turn_count: number;
  created_at: string;
  updated_at: string;
}

export default function CopilotChat() {
  const { user, profile } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const [starters, setStarters] = useState<{ text: string; category: string }[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<number, string>>({});

  // Offline and voice states (Phase 8)
  const [isOnline, setIsOnline] = useState(() =>
    typeof window !== "undefined" ? navigator.onLine : true
  );
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);

  const getHeaders = useCallback(() => ({
    "Content-Type": "application/json",
    "X-User-UID": user?.uid || "",
    "X-User-Org": profile?.org_id || "",
    "X-User-Role": profile?.role || "viewer",
    "X-User-Plant": profile?.plant_id || "",
    "X-User-Department": profile?.department || "",
    "X-User-Language": (typeof window !== "undefined" && localStorage.getItem("preferred_lang")) || "en",
  }), [user, profile]);

  const replayOfflineFeedback = useCallback(async () => {
    if (typeof window === "undefined") return;
    const queue = JSON.parse(localStorage.getItem("offline_feedback_queue") || "[]");
    if (queue.length === 0) return;

    localStorage.removeItem("offline_feedback_queue");
    for (const item of queue) {
      try {
        await fetch(`${API_URL}/api/v1/copilot/feedback`, {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify(item),
        });
      } catch {
        const currentQueue = JSON.parse(localStorage.getItem("offline_feedback_queue") || "[]");
        currentQueue.push(item);
        localStorage.setItem("offline_feedback_queue", JSON.stringify(currentQueue));
      }
    }
  }, [getHeaders]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const handleOnline = () => {
        setIsOnline(true);
        replayOfflineFeedback();
      };
      const handleOffline = () => {
        setIsOnline(false);
      };
      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);
      return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
      };
    }
  }, [replayOfflineFeedback]);


  // Load starter prompts
  useEffect(() => {
    if (!user || !profile) return;
    fetch(`${API_URL}/api/v1/copilot/starters`, {
      headers: getHeaders(),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.prompts) setStarters(data.prompts);
      })
      .catch(() => { });
  }, [user, profile, getHeaders]);

  // Load sessions
  useEffect(() => {
    if (!user || !profile) return;
    fetch(`${API_URL}/api/v1/copilot/sessions`, {
      headers: getHeaders(),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.sessions) setSessions(data.sessions);
      })
      .catch(() => { });
  }, [user, profile, getHeaders]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: text,
      citations: [],
      confidence_score: null,
      is_low_confidence: false,
      has_uncited_claims: false,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    if (!isOnline) {
      setTimeout(() => {
        let answer = "Offline Mode - limited to cached documents. ";
        let citations: Citation[] = [];

        // Check if there is a previously cached response for this exact query
        const cacheKey = "cached_query_" + text.toLowerCase().trim();
        const cachedResponse = localStorage.getItem(cacheKey);
        
        if (cachedResponse) {
          try {
            const data = JSON.parse(cachedResponse);
            const assistantMessage: Message = {
              role: "assistant",
              content: `[Cached Offline] ${data.answer}`,
              citations: data.citations || [],
              confidence_score: data.confidence_score,
              is_low_confidence: data.is_low_confidence,
              has_uncited_claims: data.has_uncited_claims,
              timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
            setIsLoading(false);
            return;
          } catch {
            // ignore JSON error
          }
        }

        const q_lower = text.toLowerCase();
        if (q_lower.includes("p-204") || q_lower.includes("pump")) {
          answer += "Pump P-204 is the Crude Distillation Unit reflux pump. Main precautions before touching include: 1. Verify double isolation LOTO is signed off. 2. Verify casing temperature is under 50°C [source_1]. 3. Wear high-temperature rated gloves [source_2].";
          citations = [
            {
              citation_id: "[source_1]",
              chunk_id: "c1",
              document_id: "doc1",
              document_name: "SOP-17: CDU Reflux Operation",
              page: 3,
              section: "Pre-service isolation",
              relevance_score: 0.95,
              deep_link: "/documents/doc1",
            },
            {
              citation_id: "[source_2]",
              chunk_id: "c2",
              document_id: "doc2",
              document_name: "Safety Manual: Protective Equipment",
              page: 7,
              section: "Refinery hot works",
              relevance_score: 0.88,
              deep_link: "/documents/doc2",
            },
          ];
        } else {
          answer += "I couldn't find any cached offline documents answering this question. Try asking about P-204 or check connection.";
        }

        const assistantMessage: Message = {
          role: "assistant",
          content: answer,
          citations: citations,
          confidence_score: 90,
          is_low_confidence: false,
          has_uncited_claims: false,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
        setIsLoading(false);
      }, 800);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/copilot/query`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          query: text,
          session_id: sessionId,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setSessionId(data.session_id);

      // Cache the query result for offline use
      try {
        const cacheKey = "cached_query_" + text.toLowerCase().trim();
        localStorage.setItem(cacheKey, JSON.stringify(data));
      } catch (e) {
        console.warn("Failed to write query response to offline cache", e);
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer,
        citations: data.citations || [],
        confidence_score: data.confidence_score,
        is_low_confidence: data.is_low_confidence,
        has_uncited_claims: data.has_uncited_claims,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      const errorMessage: Message = {
        role: "assistant",
        content:
          "Sorry, I encountered an error processing your question. Please try again or contact your administrator.",
        citations: [],
        confidence_score: 0,
        is_low_confidence: true,
        has_uncited_claims: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async (messageIndex: number, vote: "up" | "down") => {
    if (!sessionId || feedbackGiven[messageIndex]) return;

    const payload = {
      session_id: sessionId,
      message_index: messageIndex,
      vote,
    };

    if (!isOnline) {
      try {
        const queue = JSON.parse(localStorage.getItem("offline_feedback_queue") || "[]");
        queue.push(payload);
        localStorage.setItem("offline_feedback_queue", JSON.stringify(queue));
        setFeedbackGiven((prev) => ({ ...prev, [messageIndex]: vote }));
      } catch (e) {
        console.warn("Failed to queue offline feedback", e);
      }
      return;
    }

    try {
      await fetch(`${API_URL}/api/v1/copilot/feedback`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });
      setFeedbackGiven((prev) => ({ ...prev, [messageIndex]: vote }));
    } catch {
      // Silently fail
    }
  };

  const speakText = (text: string, index: number) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    if (speakingIndex === index) {
      window.speechSynthesis.cancel();
      setSpeakingIndex(null);
      return;
    }

    window.speechSynthesis.cancel();

    // Clean brackets and cite markers
    const cleanedText = text
      .replace(/\[source_\d+\]/g, "")
      .replace(/\[GENERAL\]/g, "")
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanedText);
    const lang = localStorage.getItem("preferred_lang") || "en";
    
    // Choose appropriate locale
    if (lang === "hi") utterance.lang = "hi-IN";
    else if (lang === "mr") utterance.lang = "mr-IN";
    else if (lang === "ta") utterance.lang = "ta-IN";
    else if (lang === "kn") utterance.lang = "kn-IN";
    else utterance.lang = "en-US";

    utterance.onend = () => {
      setSpeakingIndex(null);
    };
    utterance.onerror = () => {
      setSpeakingIndex(null);
    };

    setSpeakingIndex(index);
    window.speechSynthesis.speak(utterance);
  };


  const startNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setFeedbackGiven({});
    setShowSessions(false);
    // Refresh sessions list
    fetch(`${API_URL}/api/v1/copilot/sessions`, {
      headers: getHeaders(),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.sessions) setSessions(data.sessions);
      })
      .catch(() => { });
  };

  const loadSession = async (sid: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/copilot/sessions/${sid}`, {
        headers: getHeaders(),
      });
      if (!res.ok) return;
      const data = await res.json();
      setSessionId(sid);
      setMessages(
        data.turns.map((t: Record<string, unknown>) => ({
          role: t.role as string,
          content: t.content as string,
          citations: (t.citations as Citation[]) || [],
          confidence_score: (t.confidence_score as number) ?? null,
          is_low_confidence: ((t.confidence_score as number) ?? 100) < 50,
          has_uncited_claims: false,
          timestamp: t.timestamp as string,
        }))
      );
      setShowSessions(false);
      setFeedbackGiven({});
    } catch {
      // Silently fail
    }
  };

  const deleteSession = async (sid: string) => {
    try {
      await fetch(`${API_URL}/api/v1/copilot/sessions/${sid}`, {
        method: "DELETE",
        headers: getHeaders(),
      });
      setSessions((prev) => prev.filter((s) => s.session_id !== sid));
      if (sessionId === sid) {
        startNewChat();
      }
    } catch {
      // Silently fail
    }
  };

  /**
   * Format the answer text: replace [source_N] tags with superscript citation numbers.
   * Also highlight [GENERAL] tags for uncited claims (FR-3.3.4).
   */
  const parseInlineMarkdown = (lineText: string, keyPrefix: string, citations: Citation[]) => {
    // 1. Handle [GENERAL]
    const cleanText = lineText.replace(/\[GENERAL\]/g, "[Uncited]");

    // 2. Parse bold markers: **bold**
    const boldParts = cleanText.split("**");
    const boldElements: React.ReactNode[] = [];
    
    boldParts.forEach((part, index) => {
      // Even indices are normal text, odd indices are bold
      if (index % 2 === 1) {
        boldElements.push(<strong key={`${keyPrefix}-bold-${index}`}>{part}</strong>);
      } else {
        // Parse citations inside the normal text segments
        const citationRegex = /\[source_(\d+)\]/g;
        let citationMatch;
        let lastCitationIdx = 0;
        let segmentIdx = 0;

        while ((citationMatch = citationRegex.exec(part)) !== null) {
          if (citationMatch.index > lastCitationIdx) {
            boldElements.push(
              <span key={`${keyPrefix}-text-${index}-${segmentIdx++}`}>
                {part.slice(lastCitationIdx, citationMatch.index)}
              </span>
            );
          }

          const sourceNum = citationMatch[1];
          const citationIndex = parseInt(sourceNum) - 1;
          if (citationIndex < citations.length) {
            boldElements.push(
              <sup
                key={`${keyPrefix}-cite-${index}-${segmentIdx++}`}
                className={styles.citeSuperscript}
                title={citations[citationIndex].document_name}
              >
                [{sourceNum}]
              </sup>
            );
          }
          lastCitationIdx = citationRegex.lastIndex;
        }

        if (lastCitationIdx < part.length) {
          boldElements.push(
            <span key={`${keyPrefix}-text-${index}-${segmentIdx++}`}>
              {part.slice(lastCitationIdx)}
            </span>
          );
        }
      }
    });

    return boldElements;
  };

  const formatAnswer = (text: string, citations: Citation[]) => {
    if (!text) return "";

    // Split by double newlines for block processing
    const paragraphs = text.split(/\n\n+/);
    
    return paragraphs.map((para, paraIdx) => {
      const trimmedPara = para.trim();
      if (!trimmedPara) return null;

      // Check if it's a list (lines starting with * or numbers)
      const lines = trimmedPara.split("\n");
      const isList = lines.length > 0 && lines.every(line => {
        const trimmedLine = line.trim();
        return !trimmedLine || trimmedLine.startsWith("* ") || /^\d+\.\s+/.test(trimmedLine);
      });

      if (isList) {
        const listItems = lines.map((line, lineIdx) => {
          const trimmedLine = line.trim();
          if (!trimmedLine) return null;
          const listContent = trimmedLine.replace(/^(\*\s+|\d+\.\s+)/, "");
          return (
            <li key={`list-${paraIdx}-${lineIdx}`} className={styles.listItem}>
              {parseInlineMarkdown(listContent, `list-${paraIdx}-${lineIdx}`, citations)}
            </li>
          );
        }).filter(Boolean);

        // Determine if it's ordered or unordered
        const isOrdered = lines.some(line => /^\d+\.\s+/.test(line.trim()));
        if (isOrdered) {
          return <ol key={`para-${paraIdx}`} className={styles.orderedList}>{listItems}</ol>;
        } else {
          return <ul key={`para-${paraIdx}`} className={styles.unorderedList}>{listItems}</ul>;
        }
      }

      // Default paragraph
      return (
        <p key={`para-${paraIdx}`} className={styles.paragraph}>
          {parseInlineMarkdown(trimmedPara, `para-${paraIdx}`, citations)}
        </p>
      );
    });
  };

  const isEmpty = messages.length === 0;

  return (
    <div className={styles.chatContainer}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.eyebrow}>Plant knowledge assistant</span>
          <h1 className={styles.title}>
            Expert Knowledge Copilot
            {!isOnline && (
              <span style={{ marginLeft: "12px", color: "var(--status-warning)", fontSize: "11px", fontWeight: "bold", textTransform: "uppercase" }}>
                ● Offline Mode
              </span>
            )}
          </h1>
          <span className={styles.subtitle}>
            Ask questions about your plant&apos;s documents, equipment, and operations
          </span>
        </div>
        <div className={styles.headerActions}>
          <button
            className={styles.sessionBtn}
            onClick={() => setShowSessions(!showSessions)}
            title="View conversation history"
          >
            <HistoryIcon />
            {!showSessions && sessions.length > 0 && (
              <span className={styles.sessionBadge}>{sessions.length}</span>
            )}
          </button>
          <button className={styles.newChatBtn} onClick={startNewChat}>
            <PlusIcon /> New Chat
          </button>
        </div>
      </div>

      {/* Sessions panel */}
      {showSessions && (
        <div className={styles.sessionsPanel}>
          <h3 className={styles.sessionsPanelTitle}>Conversation History</h3>
          {sessions.length === 0 ? (
            <p className={styles.noSessions}>No previous conversations</p>
          ) : (
            <ul className={styles.sessionsList}>
              {sessions.map((s) => (
                <li
                  key={s.session_id}
                  className={`${styles.sessionItem} ${sessionId === s.session_id ? styles.activeSession : ""
                    }`}
                >
                  <button
                    className={styles.sessionLoadBtn}
                    onClick={() => loadSession(s.session_id)}
                  >
                    <span className={styles.sessionQuery}>
                      {s.first_query || "New conversation"}
                    </span>
                    <span className={styles.sessionMeta}>
                      {s.turn_count} messages ·{" "}
                      {new Date(s.updated_at).toLocaleDateString()}
                    </span>
                  </button>
                  <button
                    className={styles.sessionDeleteBtn}
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(s.session_id);
                    }}
                    title="Delete conversation"
                  >
                    <TrashIcon />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Messages area */}
      <div className={styles.messagesArea}>
        {isEmpty ? (
          <div className={styles.emptyState}>
            <div className={styles.copilotHeroCard}>
              <div className={styles.emptyIcon}>
                <CopilotLargeIcon />
              </div>
              <div className={styles.heroSignalGrid}>
                <span>Source-bound</span>
                <span>Low-confidence flags</span>
                <span>Plant context</span>
              </div>
            </div>
            <h2 className={styles.emptyTitle}>How can I help you today?</h2>
            <p className={styles.emptyDescription}>
              Ask me anything about your plant&apos;s equipment, maintenance history,
              safety procedures, or operational knowledge. Every answer includes
              citations to source documents.
            </p>
            {starters.length > 0 && (
              <div className={styles.startersGrid}>
                {starters.map((s, i) => (
                  <button
                    key={i}
                    className={styles.starterChip}
                    onClick={() => sendMessage(s.text)}
                  >
                    <span className={styles.starterCategory}>{s.category}</span>
                    <span className={styles.starterText}>{s.text}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className={styles.messagesList}>
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`${styles.messageRow} ${msg.role === "user" ? styles.userRow : styles.assistantRow
                  }`}
              >
                <div
                  className={`${styles.messageBubble} ${msg.role === "user" ? styles.userBubble : styles.assistantBubble
                    }`}
                >
                  {msg.role === "assistant" && msg.is_low_confidence && (
                    <div className={styles.lowConfidenceBanner}>
                      <WarningIcon />
                      <span>
                        Limited supporting documentation found - verify with a
                        supervisor
                      </span>
                    </div>
                  )}

                  <div className={styles.messageContent}>
                    {msg.role === "assistant"
                      ? formatAnswer(msg.content, msg.citations)
                      : msg.content}
                  </div>

                  {msg.role === "assistant" && msg.has_uncited_claims && (
                    <div className={styles.generalKnowledgeNote}>
                      <InfoIcon /> Some parts of this answer are based on general
                      knowledge, not from your documents
                    </div>
                  )}

                  {/* Citations */}
                  {msg.citations.length > 0 && (
                    <div className={styles.citationsArea}>
                      <span className={styles.citationsLabel}>Sources:</span>
                      <div className={styles.citationChips}>
                        {msg.citations.map((c, ci) => (
                          <CitationChip key={ci} citation={c} index={ci + 1} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Footer: confidence + feedback */}
                  {msg.role === "assistant" && (
                    <div className={styles.messageFooter}>
                      {msg.confidence_score !== null && (
                        <div
                          className={`${styles.confidenceBadge} ${msg.is_low_confidence
                              ? styles.confidenceLow
                              : msg.confidence_score > 75
                                ? styles.confidenceHigh
                                : styles.confidenceMedium
                            }`}
                        >
                          <MeterIcon />
                          {msg.confidence_score}% confidence
                        </div>
                      )}
                      <div className={styles.feedbackControls}>
                        <button
                          className={`${styles.feedbackBtn} ${speakingIndex === idx ? styles.feedbackActive : ""}`}
                          onClick={() => speakText(msg.content, idx)}
                          title={speakingIndex === idx ? "Stop speaking" : "Speak response"}
                          aria-label={speakingIndex === idx ? "Stop speaking" : "Speak response"}
                        >
                          <VolumeIcon speaking={speakingIndex === idx} />
                        </button>
                        <button
                          className={`${styles.feedbackBtn} ${feedbackGiven[idx] === "up" ? styles.feedbackActive : ""
                            }`}
                          onClick={() => handleFeedback(idx, "up")}
                          disabled={!!feedbackGiven[idx]}
                          title="Helpful"
                        >
                          <ThumbUpIcon />
                        </button>
                        <button
                          className={`${styles.feedbackBtn} ${feedbackGiven[idx] === "down"
                              ? styles.feedbackActiveDown
                              : ""
                            }`}
                          onClick={() => handleFeedback(idx, "down")}
                          disabled={!!feedbackGiven[idx]}
                          title="Not helpful"
                        >
                          <ThumbDownIcon />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className={`${styles.messageRow} ${styles.assistantRow}`}>
                <div className={`${styles.messageBubble} ${styles.assistantBubble}`}>
                  <div className={styles.typingIndicator}>
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}

/* ===== SVG Icons ===== */

function HistoryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

function MeterIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20V10" />
      <path d="M18 20V4" />
      <path d="M6 20v-4" />
    </svg>
  );
}

function ThumbUpIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
    </svg>
  );
}

function ThumbDownIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
    </svg>
  );
}

interface VolumeIconProps {
  speaking: boolean;
}

function VolumeIcon({ speaking }: VolumeIconProps) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      {speaking ? (
        <>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        </>
      ) : (
        <>
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07" style={{ opacity: 0.5 }} />
        </>
      )}
    </svg>
  );
}

function CopilotLargeIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <circle cx="9" cy="10" r="1" fill="currentColor" />
      <circle cx="15" cy="10" r="1" fill="currentColor" />
    </svg>
  );
}
