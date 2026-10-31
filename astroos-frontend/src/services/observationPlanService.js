import api from "./api";

export function parseObservationPlan(data = {}) {
  const recommendations = data.recommendations || data.recommendation || {};

  return {
    status: data.status || "unknown",
    eventCount:
      data.event_count ??
      data.database_events_found ??
      (data.ranked_events ? data.ranked_events.length : 0),
    ranked:
      data.ranked_events ||
      recommendations.ranked_events ||
      recommendations.rankedEvents ||
      [],
    schedule:
      recommendations.schedule ||
      recommendations.scheduled_events ||
      recommendations.scheduledEvents ||
      [],
    skipped:
      recommendations.skipped_events ||
      recommendations.unscheduled_events ||
      recommendations.skippedEvents ||
      [],
    details: recommendations.details || recommendations.events || [],
    summary: recommendations.summary || {},
    explanation:
      recommendations.explanation ||
      recommendations.overall_explanation ||
      data.explanation,
    databaseEventsFound: data.database_events_found ?? null,
    databaseEventsRejected: data.database_events_rejected ?? [],
    dataQuality: data.data_quality || {},
    raw: data,
  };
}

export const observationPlanService = {
  async generate(payload) {
    const response = await api.post("/api/v1/observation-plans/generate", payload, {
      timeout: 120000,
    });
    return parseObservationPlan(response.data);
  },
};
