import api from "./api";

export const visibilityService = {
  async calculate(payload) {
    const response = await api.post(
      "/api/v1/visibility-assessments/calculate",
      payload,
      { timeout: 60000 }
    );
    return response.data;
  },

  async getByEvent(eventId) {
    const response = await api.get(
      `/api/v1/visibility-assessments/by-event/${eventId}`
    );
    return response.data;
  },
};
