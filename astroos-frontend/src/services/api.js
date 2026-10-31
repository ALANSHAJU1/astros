import axios from "axios";

export const ACCESS_TOKEN_KEY = "astroos_access_token";
export const REFRESH_TOKEN_KEY = "astroos_refresh_token";
export const AUTH_EXPIRED_EVENT = "astroos-auth-expired";
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

const refreshClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

let refreshPromise = null;

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function storeTokens(tokens = {}) {
  if (tokens.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  }
  if (tokens.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export async function refreshSession() {
  const refresh_token = getRefreshToken();
  if (!refresh_token) {
    throw new Error("No refresh token is stored.");
  }

  const response = await refreshClient.post("/api/v1/auth/refresh", {
    refresh_token,
  });

  storeTokens(response.data);
  return response.data;
}

function isAuthEndpoint(url = "") {
  return (
    url.includes("/api/v1/auth/login") ||
    url.includes("/api/v1/auth/register") ||
    url.includes("/api/v1/auth/refresh") ||
    url.includes("/api/v1/auth/logout")
  );
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;

    if (status === 401 && !original._retry && !isAuthEndpoint(original.url || "")) {
      original._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = refreshSession().finally(() => {
            refreshPromise = null;
          });
        }

        await refreshPromise;
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${getAccessToken()}`;
        return api(original);
      } catch {
        clearTokens();
        window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
      }
    }

    console.error("AstroOS API error:", error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
