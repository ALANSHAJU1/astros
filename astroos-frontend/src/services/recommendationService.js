import api from "./api";

export const recommendationService = {
  async fromDatabase(payload) {
    const response = await api.post(
      "/api/v1/recommendations/from-database",
      payload,
      { timeout: 60000 }
    );
    return response.data;
  },
};
