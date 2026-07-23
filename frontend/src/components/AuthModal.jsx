import React, { useState, useEffect } from 'react';
import { X, Lock, Mail, User, ShieldCheck, Check, AlertCircle, ArrowRight, RefreshCw, KeyRound, Eye, EyeOff } from 'lucide-react';
import { api, setAuthToken } from '../api';

export default function AuthModal({ onClose, onSuccess }) {
  // Modes: 'login', 'register_init', 'register_otp', 'forgot_init', 'forgot_otp'
  const [mode, setMode] = useState('login');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');

  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // 2-minute countdown timer state (120 seconds)
  const [timeLeft, setTimeLeft] = useState(120);

  useEffect(() => {
    let timer;
    if ((mode === 'register_otp' || mode === 'forgot_otp') && timeLeft > 0) {
      timer = setInterval(() => setTimeLeft((prev) => prev - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [mode, timeLeft]);

  // Live password validation checks
  const checkPasswordRules = (pw) => {
    return {
      length: pw.length >= 8,
      uppercase: /[A-Z]/.test(pw),
      lowercase: /[a-z]/.test(pw),
      number: /[0-9]/.test(pw),
      special: /[!@#$%^&*(),.?":{}|<>]/.test(pw),
    };
  };

  const currentRules = checkPasswordRules(mode === 'forgot_otp' ? newPassword : password);
  const isPasswordStrong = Object.values(currentRules).every(Boolean);

  // Handle Login Submission
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.login(email, password);
      setAuthToken(res.access_token);
      const me = await api.getMe();
      onSuccess(me);
      onClose();
    } catch (err) {
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Send Register OTP
  const handleRegisterInit = async (e) => {
    e.preventDefault();
    if (!isPasswordStrong) {
      setError('Please satisfy all strong password criteria before proceeding.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.sendRegisterOTP(email, password, fullName);
      setSuccessMsg('Verification OTP sent to your email (Valid for 2 mins).');
      setTimeLeft(120);
      setMode('register_otp');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Verify Register OTP
  const handleRegisterOTPVerify = async (e) => {
    e.preventDefault();
    if (!otp || otp.length < 4) {
      setError('Please enter the valid 6-digit OTP code.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.verifyRegisterOTP(email, password, fullName, otp);
      setAuthToken(res.access_token);
      const me = await api.getMe();
      onSuccess(me);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };



  // Step 1: Request Forgot Password OTP
  const handleForgotInit = async (e) => {
    e.preventDefault();
    if (!email) {
      setError('Please enter your registered email address.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api.requestForgotOTP(email);
      setSuccessMsg('Reset OTP sent to your email (Valid for 2 mins).');
      setTimeLeft(120);
      setMode('forgot_otp');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Reset Password with OTP
  const handleForgotOTPReset = async (e) => {
    e.preventDefault();
    if (!isPasswordStrong) {
      setError('New password must satisfy all strong password requirements.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.resetForgotPassword(email, otp, newPassword);
      setSuccessMsg(res.message || 'Password reset successful! Please log in with your new password.');
      setMode('login');
      setPassword('');
      setOtp('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="glass-panel max-w-md w-full p-6 sm:p-8 relative shadow-2xl border border-slate-800">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/60 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-400 flex items-center justify-center mx-auto mb-3">
            {mode.includes('forgot') ? (
              <KeyRound className="w-6 h-6" />
            ) : mode.includes('otp') ? (
              <ShieldCheck className="w-6 h-6" />
            ) : (
              <Lock className="w-6 h-6" />
            )}
          </div>

          <h2 className="text-2xl font-bold text-slate-100">
            {mode === 'login' && 'Welcome Back'}
            {mode === 'register_init' && 'Create Your Account'}
            {mode === 'register_otp' && 'Verify Email OTP'}
            {mode === 'forgot_init' && 'Reset Password'}
            {mode === 'forgot_otp' && 'Verify Reset OTP'}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {mode === 'login' && 'Sign in to access your saved job application workflow.'}
            {mode === 'register_init' && 'Register with email verification & strong password security.'}
            {mode === 'register_otp' && `Enter 6-digit OTP code sent to ${email}`}
            {mode === 'forgot_init' && 'Enter your registered email address to receive password reset OTP.'}
            {mode === 'forgot_otp' && 'Enter OTP and set your new strong password.'}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-950/60 border border-red-500/40 rounded-xl text-xs text-red-300 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 bg-emerald-950/60 border border-emerald-500/40 rounded-xl text-xs text-emerald-300 flex items-center space-x-2">
            <Check className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* MODE: LOGIN */}
        {mode === 'login' && (
          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your.name@example.com"
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Password</label>
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode('forgot_init');
                  }}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
                >
                  Forgot Password?
                </button>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-10 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 p-0.5"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary text-xs py-3 flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/20"
            >
              <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setSuccessMsg(null);
                  setMode('register_init');
                }}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Don't have an account? Register
              </button>
            </div>
          </form>
        )}

        {/* MODE: REGISTER INIT */}
        {mode === 'register_init' && (
          <form onSubmit={handleRegisterInit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Shashank Jain"
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="realshashankjain@gmail.com"
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Strong Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="e.g. Pass#2026!Key"
                  className="w-full pl-9 pr-10 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 p-0.5"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>


              {/* Password strength visual rules indicator */}
              <div className="mt-2.5 grid grid-cols-2 gap-1.5 p-2.5 bg-slate-900/60 rounded-xl border border-slate-800 text-[11px]">
                <span className={currentRules.length ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.length ? '✓' : '•'} 8+ Characters
                </span>
                <span className={currentRules.uppercase ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.uppercase ? '✓' : '•'} Upper Letter (A-Z)
                </span>
                <span className={currentRules.lowercase ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.lowercase ? '✓' : '•'} Lower Letter (a-z)
                </span>
                <span className={currentRules.number ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.number ? '✓' : '•'} Number (0-9)
                </span>
                <span className={`col-span-2 ${currentRules.special ? 'text-emerald-400 font-semibold' : 'text-slate-500'}`}>
                  {currentRules.special ? '✓' : '•'} Special Char (!@#$%^&*)
                </span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !isPasswordStrong}
              className="w-full btn-primary text-xs py-3 flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/20 disabled:opacity-40"
            >
              <span>{loading ? 'Sending OTP...' : 'Send Verification OTP'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setSuccessMsg(null);
                  setMode('login');
                }}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Already have an account? Sign In
              </button>
            </div>
          </form>
        )}

        {/* MODE: REGISTER OTP */}
        {mode === 'register_otp' && (
          <form onSubmit={handleRegisterOTPVerify} className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">6-Digit OTP Code</label>
                <span className={`text-xs font-mono font-bold ${timeLeft < 30 ? 'text-red-400 animate-pulse' : 'text-cyan-400'}`}>
                  Expires in: {formatTime(timeLeft)}
                </span>
              </div>
              <input
                type="text"
                maxLength={6}
                required
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="123456"
                className="w-full tracking-widest text-center text-lg font-mono py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-slate-100"
              />
            </div>

            <button
              type="submit"
              disabled={loading || timeLeft === 0}
              className="w-full btn-primary text-xs py-3 flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/20 disabled:opacity-40"
            >
              <span>{loading ? 'Verifying...' : 'Verify OTP & Complete Registration'}</span>
            </button>

            <div className="flex items-center justify-between text-xs pt-2">
              <button
                type="button"
                onClick={handleRegisterInit}
                disabled={loading}
                className="text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Resend OTP</span>
              </button>

              <button
                type="button"
                onClick={() => setMode('register_init')}
                className="text-slate-400 hover:text-slate-200"
              >
                Back
              </button>
            </div>
          </form>
        )}

        {/* MODE: FORGOT INIT */}
        {mode === 'forgot_init' && (
          <form onSubmit={handleForgotInit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Registered Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="realshashankjain@gmail.com"
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary text-xs py-3 flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/20"
            >
              <span>{loading ? 'Sending OTP...' : 'Send Password Reset OTP'}</span>
            </button>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  setSuccessMsg(null);
                  setMode('login');
                }}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Remember password? Back to Sign In
              </button>
            </div>
          </form>
        )}

        {/* MODE: FORGOT OTP */}
        {mode === 'forgot_otp' && (
          <form onSubmit={handleForgotOTPReset} className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">6-Digit Reset OTP</label>
                <span className={`text-xs font-mono font-bold ${timeLeft < 30 ? 'text-red-400 animate-pulse' : 'text-cyan-400'}`}>
                  Expires in: {formatTime(timeLeft)}
                </span>
              </div>
              <input
                type="text"
                maxLength={6}
                required
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="123456"
                className="w-full tracking-widest text-center text-lg font-mono py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-slate-100"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">New Strong Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type={showNewPassword ? "text" : "password"}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="e.g. NewPass#2026!"
                  className="w-full pl-9 pr-10 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 p-0.5"
                >
                  {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>


              {/* Password strength rules */}
              <div className="mt-2.5 grid grid-cols-2 gap-1.5 p-2.5 bg-slate-900/60 rounded-xl border border-slate-800 text-[11px]">
                <span className={currentRules.length ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.length ? '✓' : '•'} 8+ Characters
                </span>
                <span className={currentRules.uppercase ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.uppercase ? '✓' : '•'} Upper Letter (A-Z)
                </span>
                <span className={currentRules.lowercase ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.lowercase ? '✓' : '•'} Lower Letter (a-z)
                </span>
                <span className={currentRules.number ? 'text-emerald-400 font-semibold' : 'text-slate-500'}>
                  {currentRules.number ? '✓' : '•'} Number (0-9)
                </span>
                <span className={`col-span-2 ${currentRules.special ? 'text-emerald-400 font-semibold' : 'text-slate-500'}`}>
                  {currentRules.special ? '✓' : '•'} Special Char (!@#$%^&*)
                </span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !isPasswordStrong || timeLeft === 0}
              className="w-full btn-primary text-xs py-3 flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/20 disabled:opacity-40"
            >
              <span>{loading ? 'Resetting Password...' : 'Verify OTP & Reset Password'}</span>
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
