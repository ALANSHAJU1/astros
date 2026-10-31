import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { AUTH_EXPIRED_EVENT, getAccessToken } from "../services/api";
import { authService } from "../services/authService";
import { getApiErrorMessage } from "../utils/apiErrors";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const hydrate = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setReady(true);
      return;
    }

    try {
      const profile = await authService.me();
      setUser(profile);
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    hydrate();

    function onExpired() {
      setUser(null);
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [hydrate]);

  const login = useCallback(async (email, password) => {
    await authService.login(email, password);
    const profile = await authService.me();
    setUser(profile);
    return profile;
  }, []);

  const register = useCallback(async (payload) => {
    return authService.register(payload);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (error) {
      console.error(getApiErrorMessage(error, "Logout did not complete cleanly."));
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      ready,
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === "admin",
      login,
      register,
      logout,
      refreshProfile: hydrate,
    }),
    [user, ready, login, register, logout, hydrate]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
