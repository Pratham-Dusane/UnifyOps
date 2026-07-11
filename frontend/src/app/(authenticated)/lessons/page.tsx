import PlaceholderPage from "@/components/PlaceholderPage/PlaceholderPage";

export default function LessonsPage() {
  return (
    <PlaceholderPage
      title="Lessons Learned"
      description="Cross-incident pattern detection that surfaces systemic failure patterns invisible to any individual review, with proactive warnings pushed to teams before similar conditions recur."
      phase="Phase 6"
      features={[
        "Incident and near-miss enrichment pipeline",
        "Cross-incident pattern detection agent",
        "Proactive warning notifications",
        "Searchable lessons learned repository",
        "Pattern-to-failure library cross-referencing",
        "Alert deduplication and rate limiting",
      ]}
    />
  );
}
