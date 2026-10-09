import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { identity, subscribeIdentity } from '../identity/runtime';
import { getMe, registerUnauthorizedHandler } from './api';
const AuthContext = createContext(null);
export function AuthProvider({children}) {
  const [user,setUser]=useState(null);
  const [loading,setLoading]=useState(true);
  const [authNotice,setAuthNotice]=useState('');
  const clear=useCallback(() => setUser(null),[]);
  useEffect(() => {
    let mounted=true;
    const unsubscribe=subscribeIdentity(event => {
      if (mounted) {setUser(null);if(event==='expired')setAuthNotice('Your session expired. Sign in again.');}
      if (mounted && event==='rejected')setAuthNotice('The authentication response was rejected. Sign in again.');
    });
    registerUnauthorizedHandler(() => { identity.expire(); });
    identity.init().then(async authenticated => {
      if(authenticated) {const me=await getMe();if(mounted)setUser(me);}
    }).catch(() => {if(mounted)setAuthNotice('Sign-in is unavailable or the authentication response was rejected. Try again.');})
      .finally(() => {if(mounted)setLoading(false);});
    return () => {mounted=false;unsubscribe();registerUnauthorizedHandler(null);};
  },[]);
  const refreshMe=useCallback(async () => {const me=await getMe();setUser(me);return me;},[]);
  const login=useCallback(async () => {setAuthNotice('');await identity.login();},[]);
  const logout=useCallback(async () => {clear();await identity.logout();},[clear]);
  return <AuthContext.Provider value={{user,role:user?.role||'',loading,isAuthenticated:Boolean(user),
    authNotice,setAuthNotice,login,logout,refreshMe}}>{children}</AuthContext.Provider>;
}
export function useAuth() {return useContext(AuthContext);}
