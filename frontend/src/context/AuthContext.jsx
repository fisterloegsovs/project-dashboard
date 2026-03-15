import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      localStorage.removeItem("token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (credentials) => {
    const result = await api.login(credentials);
    localStorage.setItem("token", result.token);
    setUser(result.user);
    // Reload full user (with teams)
    const me = await api.getMe();
    setUser(me);
    return me;
  };

  const register = async (data) => {
    const result = await api.register(data);
    localStorage.setItem("token", result.token);
    setUser(result.user);
    const me = await api.getMe();
    setUser(me);
    return me;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  const refreshUser = async () => {
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      // ignore
    }
  };

  // RBAC helpers
  const getUserRoleInTeam = (teamId) => {
    if (!user?.teams) return null;
    const team = user.teams.find((t) => t.id === teamId);
    return team?.role || null;
  };

  const canModify = (teamId) => {
    if (!teamId) return true;
    const role = getUserRoleInTeam(teamId);
    return role === "admin" || role === "member";
  };

  const canAdmin = (teamId) => {
    if (!teamId) return true;
    return getUserRoleInTeam(teamId) === "admin";
  };

  const canView = (teamId) => {
    if (!teamId) return true;
    return getUserRoleInTeam(teamId) !== null;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refreshUser,
        getUserRoleInTeam,
        canModify,
        canAdmin,
        canView,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
