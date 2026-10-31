import api from "./api";

export const environmentalService = {
  async getLatestByLocation({ latitude, longitude }) {
    const response = await api.get(
      "/api/v1/environmental-observations/latest/by-location",
      { params: { latitude, longitude } }
    );
    return response.data;
  },

  async getByLocation({ latitude, longitude, start_time, end_time, limit = 48 }) {
    const response = await api.get(
      "/api/v1/environmental-observations/by-location",
      {
        params: {
          latitude,
          longitude,
          start_time,
          end_time,
          limit,
        },
      }
    );
    return response.data;
  },
};
