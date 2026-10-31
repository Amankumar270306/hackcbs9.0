import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi, setAccessToken, getAccessToken } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [activeOrg, setActiveOrg] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const switchOrganization = useCallback((orgId) => {
    const selected = organizations.find((o) => o.organization_id === orgId);
    if (selected) {
      setActiveOrg(selected);
      localStorage.setItem('sentinel_active_org_id', orgId);
    }
  }, [organizations]);

  const loadCurrentUser = useCallback(async () => {
    try {
      const data = await authApi.getMe();
      setUser({
        id: data.id,
        email: data.email,
        full_name: data.full_name,
        is_active: data.is_active,
      });

      const orgs = data.organizations || [];
      setOrganizations(orgs);

      const savedOrgId = localStorage.getItem('sentinel_active_org_id');
      const matchedOrg = orgs.find((o) => o.organization_id === savedOrgId);

      if (matchedOrg) {
        setActiveOrg(matchedOrg);
      } else if (orgs.length > 0) {
        setActiveOrg(orgs[0]);
        localStorage.setItem('sentinel_active_org_id', orgs[0].organization_id);
      } else {
        setActiveOrg(null);
      }
      return true;
    } catch (err) {
      setUser(null);
      setOrganizations([]);
      setActiveOrg(null);
      setAccessToken(null);
      return false;
    }
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      // Try to load current user if access token or refresh cookie exists
      await loadCurrentUser();
      setIsLoading(false);
    };

    initAuth();

    const handleExpired = () => {
      setUser(null);
      setOrganizations([]);
      setActiveOrg(null);
      setAccessToken(null);
    };

    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, [loadCurrentUser]);

  const login = async (email, password) => {
    const res = await authApi.login({ email, password });
    setAccessToken(res.access_token);
    await loadCurrentUser();
    return res;
  };

  const register = async (fullName, email, password, orgName) => {
    const res = await authApi.register({
      full_name: fullName,
      email,
      password,
      organization_name: orgName,
    });
    setAccessToken(res.access_token);
    await loadCurrentUser();
    return res;
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (err) {
      console.warn('Logout API call failed:', err);
    } finally {
      setAccessToken(null);
      setUser(null);
      setOrganizations([]);
      setActiveOrg(null);
      localStorage.removeItem('sentinel_active_org_id');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        organizations,
        activeOrg,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        switchOrganization,
        refreshProfile: loadCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

