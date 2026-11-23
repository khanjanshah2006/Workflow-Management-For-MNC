import React, { createContext, useContext, useState, useEffect } from "react";
import { authApi } from "../api/authApi";
import { setStoredToken, getStoredToken } from "../api/client";
import { setSession, clearSession, normalizeRole } from "../auth/session";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    if (typeof localStorage === "undefined") return null;
    try {
      const saved = localStorage.getItem("wms_user");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [token, setToken] = useState(() => getStoredToken() || null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore and verify active session on boot
  useEffect(() => {
    let isMounted = true;

    const initAuth = async () => {
      const existingToken = getStoredToken();
      if (existingToken) {
        setToken(existingToken);
        try {
          // Query GET /api/v1/auth/me to confirm token validity
          const meResponse = await authApi.getMe();
          const verifiedUser = meResponse?.user || meResponse;
          if (isMounted && verifiedUser) {
            const normalizedUser = {
              account_id: verifiedUser.account_id || "",
              email: verifiedUser.email || "",
              user_type: verifiedUser.user_type || "",
              role: verifiedUser.role || verifiedUser.user_type || "",
              is_active: Boolean(verifiedUser.is_active),
              emp_id: verifiedUser.emp_id ?? null,
              led_team_ids: Array.isArray(verifiedUser.led_team_ids) ? verifiedUser.led_team_ids : [],
              team_ids: Array.isArray(verifiedUser.team_ids) ? verifiedUser.team_ids : [],
              active_elevated_roles: Array.isArray(verifiedUser.active_elevated_roles) ? verifiedUser.active_elevated_roles : [],
            };
            setUser(normalizedUser);
            setSession({ access_token: existingToken, user: normalizedUser });
            localStorage.setItem("wms_user", JSON.stringify(normalizedUser));
          }
        } catch (err) {
          // If token rejected with 401, clear credentials
          if (err?.status === 401) {
            clearSession();
            setStoredToken("");
            if (typeof localStorage !== "undefined") {
              localStorage.removeItem("wms_user");
            }
            if (isMounted) {
              setUser(null);
              setToken(null);
            }
          }
        }
      }
      if (isMounted) {
        setIsLoading(false);
      }
    };

    initAuth();
    return () => {
      isMounted = false;
    };
  }, []);

  /**
   * Submits login credentials to POST /api/v1/auth/login.
   * On success, stores token in state/storage, queries GET /api/v1/auth/me,
   * stores user in state/storage, and returns verified profile.
   */
  const login = async (credentials) => {
    setIsLoading(true);
    try {
      // 1. POST /api/v1/auth/login
      const data = await authApi.login(credentials);
      const accessToken = data.access_token || data.token;

      if (!accessToken) {
        throw new Error("Authentication failed: No access token returned.");
      }

      setToken(accessToken);
      setStoredToken(accessToken);

      // 2. Query GET /api/v1/auth/me
      let authenticatedUser = data.user || null;
      try {
        const meResponse = await authApi.getMe();
        authenticatedUser = meResponse?.user || meResponse || authenticatedUser;
      } catch (meError) {
        console.warn("GET /api/v1/auth/me check completed with fallback user:", meError?.message);
      }

      const normalizedUser = authenticatedUser
        ? {
            account_id: authenticatedUser.account_id || "",
            email: authenticatedUser.email || "",
            user_type: authenticatedUser.user_type || "",
            role: authenticatedUser.role || authenticatedUser.user_type || "",
            is_active: Boolean(authenticatedUser.is_active),
            emp_id: authenticatedUser.emp_id ?? null,
            led_team_ids: Array.isArray(authenticatedUser.led_team_ids) ? authenticatedUser.led_team_ids : [],
            team_ids: Array.isArray(authenticatedUser.team_ids) ? authenticatedUser.team_ids : [],
            active_elevated_roles: Array.isArray(authenticatedUser.active_elevated_roles) ? authenticatedUser.active_elevated_roles : [],
          }
        : null;

      setUser(normalizedUser);
      setSession({
        access_token: accessToken,
        refresh_token: data.refresh_token,
        token_type: data.token_type,
        expires_in: data.expires_in,
        user: normalizedUser,
      });

      if (normalizedUser && typeof localStorage !== "undefined") {
        localStorage.setItem("wms_user", JSON.stringify(normalizedUser));
      }

      return normalizedUser;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Clears credentials and calls POST /api/v1/auth/logout.
   */
  const logout = async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setToken(null);
      clearSession();
      setStoredToken("");
      if (typeof localStorage !== "undefined") {
        localStorage.removeItem("wms_user");
      }
    }
  };

  /**
   * Validates if the user possesses one of the allowed roles.
   */
  const hasRole = (allowedRoles = []) => {
    if (!user) return false;
    const currentNorm = normalizeRole(user.user_type || user.role || "");
    return allowedRoles.some((roleItem) => {
      const targetNorm = normalizeRole(roleItem);
      return targetNorm === currentNorm;
    });
  };

  const role = user?.user_type || user?.role || null;
  const isAuthenticated = Boolean(token && user);

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        token,
        isAuthenticated,
        isLoading,
        login,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export default AuthContext;
