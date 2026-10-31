import api from "./api";

export const adminService = {
  async listUsers({ skip = 0, limit = 50 } = {}) {
    const response = await api.get("/api/v1/admin/users", {
      params: { skip, limit },
    });
    return response.data;
  },

  async updateRole(userId, role) {
    const response = await api.patch(`/api/v1/admin/users/${userId}/role`, { role });
    return response.data;
  },

  async updateStatus(userId, isActive) {
    const response = await api.patch(`/api/v1/admin/users/${userId}/status`, {
      is_active: isActive,
    });
    return response.data;
  },
};
