import api, {
  clearTokens,
  getRefreshToken,
  storeTokens,
} from "./api";

export const authService = {
  async login(email, password) {
    const response = await api.post("/api/v1/auth/login", { email, password });
    storeTokens(response.data);
    return response.data;
  },

  async register({ email, password, full_name }) {
    const response = await api.post("/api/v1/auth/register", {
      email,
      password,
      full_name: full_name || null,
    });
    return response.data;
  },

  async me() {
    const response = await api.get("/api/v1/auth/me");
    return response.data;
  },

  async logout() {
    const refresh_token = getRefreshToken();

    try {
      if (refresh_token) {
        await api.post("/api/v1/auth/logout", { refresh_token });
      }
    } finally {
      clearTokens();
    }
  },
};
