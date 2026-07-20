import { useState, useEffect } from 'react';

export interface AgentLogEntry {
  timestamp_offset_ms: number;
  agent_name: string;
  action_summary: string;
  detail?: any;
  metric?: { label: string; value: string };
}

export function useAgentStream(requestId: string | null) {
  const [logs, setLogs] = useState<AgentLogEntry[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!requestId) {
      setLogs([]);
      setIsComplete(false);
      return;
    }

    const eventSource = new EventSource(`http://localhost:8000/api/agent-console/stream?request_id=${requestId}`);

    eventSource.addEventListener('agent_step', (event) => {
      try {
        const data = JSON.parse(event.data) as AgentLogEntry;
        setLogs((prev) => [...prev, data]);
      } catch (err) {
        console.error("Failed to parse agent_step data", err);
      }
    });

    eventSource.addEventListener('done', () => {
      setIsComplete(true);
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      // Often fires on connection drop or end of stream
      console.warn("EventSource error:", err);
      setError(new Error("EventSource connection error"));
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [requestId]);

  return { logs, isComplete, error };
}
