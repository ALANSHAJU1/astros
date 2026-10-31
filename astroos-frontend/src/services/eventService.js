import api from "./api";

export const eventService = {
  async getEvents({ skip = 0, limit = 100, category } = {}) {
    const response = await api.get("/api/v1/events", {
      params: {
        skip,
        limit,
        ...(category ? { category } : {}),
      },
    });

    return response.data;
  },

  async getEvent(eventId) {
    const response = await api.get(`/api/v1/events/${eventId}`);
    return response.data;
  },
};
