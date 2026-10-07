import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  getStoredUser,
  getRole,
  getAccessToken,
  clearSession,
  saveSession,
  saveUser,
  registerUnauthorizedHandler,
  getMe,
} from '../api/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser());
  const [role, setRole] = useState(getRole());
  const [authNotice, setAuthNotice] = useState('');

  useEffect(() => {
    registerUnauthorizedHandler(() => {
      setAuthNotice('Token expired or missing. Please log in again.');
      clearSession();
      setUser(null);
      setRole('');
    });
  }, []);

  const completeLogin = useCallback((tokenData, userData) => {
    saveSession(tokenData);
    saveUser(userData);
    setUser(userData);
    setRole(userData?.role || '');
    setAuthNotice('');
  }, []);

  const refreshMe = useCallback(async () => {
    const me = await getMe();
    saveUser(me);
    setUser(me);
    setRole(me?.role || '');
    return me;
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
    setRole('');
    setAuthNotice('');
  }, []);

  const isAuthenticated = Boolean(getAccessToken()) && Boolean(user);

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        authNotice,
        setAuthNotice,
        completeLogin,
        refreshMe,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
