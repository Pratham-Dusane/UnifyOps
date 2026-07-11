import PlaceholderPage from "@/components/PlaceholderPage/PlaceholderPage";

export default function CopilotPage() {
  return (
    <PlaceholderPage
      title="Expert Knowledge Copilot"
      description="Ask questions in plain language and get trustworthy, cited answers drawn from your plant's entire documented history. Every answer includes clickable source links and a confidence score."
      phase="Phase 3"
      features={[
        "Streaming conversational chat interface",
        "Hybrid retrieval: vector + full-text + graph traversal",
        "Citation and source attribution on every answer",
        "Confidence scoring with low-confidence warnings",
        "Role-based access scoping for answers",
        "Multi-turn conversation with context memory",
      ]}
    />
  );
}
