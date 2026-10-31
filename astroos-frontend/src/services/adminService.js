import api from "./api";

export const adminService = {
  async listUsers({ skip = 0, limit = 50 } = {}) {
    const response = await api.get("/api/v1/admin/users", {
      params: { skip, limit },
    });
    return response.data;
  },
};
