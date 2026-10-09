import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Flower2 } from 'lucide-react';
import { useAuth } from '../api/AuthContext';
export default function Login() {
  const {login,loading,isAuthenticated,authNotice}=useAuth();
  const [error,setError]=useState('');
  const [starting,setStarting]=useState(false);
  if(isAuthenticated)return <Navigate to="/" replace />;
  async function begin() {
    setStarting(true);setError('');
    try {await login();}catch {setError('Unable to reach sign-in. Try again.');setStarting(false);}
  }
  return <div className="flex min-h-screen items-center justify-center bg-navy-700 p-6">
    <main className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
      <Flower2 className="mb-4 h-10 w-10 text-sage-700" />
      <h1 className="text-2xl font-bold text-navy-700">FloraSecure</h1>
      <p className="my-4 text-ink-muted">Sign in securely to access your account and orders.</p>
      {(error||authNotice)&&<p role="alert" className="mb-4 text-red-600">{error||authNotice}</p>}
      {(error||authNotice)&&<button onClick={()=>window.location.assign('/login')} className="mb-4 underline">Reload sign-in</button>}
      <button onClick={begin} disabled={loading||starting} className="btn-primary w-full">
        {loading?'Checking session…':starting?'Opening sign-in…':'Sign in'}
      </button>
    </main>
  </div>;
}
