import React, { useState, useEffect } from 'react';
import { Settings, Key, Mail, Sparkles, Save, Check, AlertCircle, ShieldCheck, UserCheck, Smartphone, Link } from 'lucide-react';
import { api } from '../api';

export default function SettingsManager() {
  const [adzunaAppId, setAdzunaAppId] = useState('');
  const [adzunaAppKey, setAdzunaAppKey] = useState('');
  const [geminiApiKey, setGeminiApiKey] = useState('');
  const [smtpServer, setSmtpServer] = useState('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpEmail, setSmtpEmail] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [dailySendLimit, setDailySendLimit] = useState(30);
  const [tosAccepted, setTosAccepted] = useState(true);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getSettings();
      setAdzunaAppId(data.adzuna_app_id || '');
      setAdzunaAppKey(data.adzuna_app_key || '');
      setGeminiApiKey(data.gemini_api_key || '');
      setSmtpServer(data.smtp_server || 'smtp.gmail.com');
      setSmtpPort(data.smtp_port || 587);
      setSmtpEmail(data.smtp_email || '');
      setPhoneNumber(data.phone_number || '');
      setLinkedinUrl(data.linkedin_url || '');
      setDailySendLimit(data.daily_send_limit ?? 30);
      setTosAccepted(data.tos_accepted ?? true);
    } catch (err) {
      console.error('Error fetching settings', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    if (!tosAccepted) {
      alert('You must accept the Terms of Service confirming that emails are sent for genuine job applications.');
      return;
    }

    setStatusMsg(null);
    try {
      await api.updateSettings({
        adzuna_app_id: adzunaAppId,
        adzuna_app_key: adzunaAppKey,
        gemini_api_key: geminiApiKey,
        smtp_server: smtpServer,
        smtp_port: parseInt(smtpPort, 10),
        smtp_email: smtpEmail,
        smtp_password: smtpPassword,
        phone_number: phoneNumber,
        linkedin_url: linkedinUrl,
        daily_send_limit: parseInt(dailySendLimit, 10),
        tos_accepted: tosAccepted,
      });
      setStatusMsg({ type: 'success', text: 'Settings & Anti-Abuse Protections updated successfully!' });
      setSmtpPassword(''); // Clear cleartext password field after save
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-slate-100">API Credentials, Profile & Anti-Abuse Safeguards</h2>
        <p className="text-xs text-slate-400">Configure your official Adzuna API keys, SMTP credentials, candidate contact info, and daily send limits.</p>
      </div>

      {statusMsg && (
        <div
          className={`p-4 rounded-xl mb-6 text-xs font-semibold flex items-center space-x-2 ${
            statusMsg.type === 'success'
              ? 'bg-emerald-950/60 border border-emerald-500/30 text-emerald-300'
              : 'bg-red-950/60 border border-red-500/30 text-red-300'
          }`}
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{statusMsg.text}</span>
        </div>
      )}

      <div className="space-y-6">
        {/* Candidate Profile Details */}
        <div className="glass-panel p-6">
          <h3 className="text-base font-bold text-slate-200 mb-2 flex items-center space-x-2">
            <UserCheck className="w-4 h-4 text-emerald-400" />
            <span>Candidate Contact Information</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            These contact details are dynamically merged into email template placeholders (`[Phone Number]`, `[LinkedIn/Portfolio Link]`).
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center space-x-1">
                <Smartphone className="w-3.5 h-3.5 text-slate-400" />
                <span>Phone Number</span>
              </label>
              <input
                type="text"
                placeholder="+91 9876543210"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center space-x-1">
                <Link className="w-3.5 h-3.5 text-slate-400" />
                <span>LinkedIn / Portfolio URL</span>
              </label>
              <input
                type="text"
                placeholder="https://linkedin.com/in/yourprofile"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>
          </div>
        </div>

        {/* Adzuna API Section */}
        <div className="glass-panel p-6">
          <h3 className="text-base font-bold text-slate-200 mb-2 flex items-center space-x-2">
            <Key className="w-4 h-4 text-indigo-400" />
            <span>Official Adzuna API Credentials</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Obtain your free official App ID and App Key from{' '}
            <a
              href="https://developer.adzuna.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-cyan-400 hover:underline"
            >
              developer.adzuna.com
            </a>
            .
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Adzuna App ID
              </label>
              <input
                type="text"
                value={adzunaAppId}
                onChange={(e) => setAdzunaAppId(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Adzuna App Key
              </label>
              <input
                type="password"
                value={adzunaAppKey}
                onChange={(e) => setAdzunaAppKey(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>
          </div>
        </div>

        {/* Option A: User's Own SMTP Account Section */}
        <div className="glass-panel p-6">
          <h3 className="text-base font-bold text-slate-200 mb-2 flex items-center space-x-2">
            <Mail className="w-4 h-4 text-cyan-400" />
            <span>Sender Email Account (Gmail / Outlook SMTP via App Password)</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Connect your personal Gmail/SMTP account using an <strong>App Password</strong> (not your regular password) so application emails are delivered genuinely from your inbox.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                SMTP Server
              </label>
              <input
                type="text"
                value={smtpServer}
                onChange={(e) => setSmtpServer(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                SMTP Port
              </label>
              <input
                type="number"
                value={smtpPort}
                onChange={(e) => setSmtpPort(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Your Email Address
              </label>
              <input
                type="email"
                placeholder="your.email@gmail.com"
                value={smtpEmail}
                onChange={(e) => setSmtpEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                App Password (16-character)
              </label>
              <input
                type="password"
                placeholder="•••• •••• •••• ••••"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
            </div>
          </div>
        </div>

        {/* Protective Measures & Anti-Abuse Safeguards */}
        <div className="glass-panel p-6 border border-amber-500/20 bg-amber-950/10">
          <h3 className="text-base font-bold text-slate-200 mb-2 flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            <span>Anti-Abuse Protective Safeguards</span>
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Protects your Gmail sender reputation and enforces legal compliance.
          </p>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Per-User Daily Send Limit (Max 20-30/day)
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={dailySendLimit}
                onChange={(e) => setDailySendLimit(e.target.value)}
                className="w-48 px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
              />
              <span className="text-[11px] text-slate-400 ml-3">Pauses sends if daily quota is reached to prevent spam flags.</span>
            </div>

            <div className="pt-2 border-t border-slate-800">
              <label className="flex items-start space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={tosAccepted}
                  onChange={(e) => setTosAccepted(e.target.checked)}
                  className="mt-1 rounded border-slate-700 bg-slate-900 text-indigo-500 w-4 h-4"
                />
                <span className="text-xs text-slate-300">
                  <strong>Mandatory Terms of Service Confirmation:</strong> I confirm that all outgoing emails sent via this platform are for genuine, individual job applications to employer HRs and not for mass commercial spam or marketing.
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Gemini AI Key Section */}
        <div className="glass-panel p-6">
          <h3 className="text-base font-bold text-slate-200 mb-2 flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>Gemini AI API Key (For AI Cover Notes)</span>
          </h3>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Gemini API Key
            </label>
            <input
              type="password"
              value={geminiApiKey}
              onChange={(e) => setGeminiApiKey(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={handleSaveSettings}
            disabled={loading}
            className="btn-primary text-xs py-3 px-6 flex items-center space-x-2"
          >
            <Save className="w-4 h-4" />
            <span>{loading ? 'Saving Settings...' : 'Save Settings & Protective Safeguards'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
