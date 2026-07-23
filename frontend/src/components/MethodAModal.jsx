import React, { useState } from 'react';
import { ExternalLink, Sparkles, Copy, Check, X, Building, MapPin } from 'lucide-react';
import { api } from '../api';

export default function MethodAModal({ job, onClose }) {
  const [coverNote, setCoverNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!job) return null;

  const handleGenerateCoverNote = async () => {
    setLoading(true);
    try {
      const res = await api.getCoverNote(job.id);
      setCoverNote(res.cover_note);
    } catch (err) {
      alert('Error generating cover note: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(coverNote);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-2xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <ExternalLink className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">Method A: Official Application</h2>
            <p className="text-xs text-slate-400">Apply directly on company portal with optional AI cover note</p>
          </div>
        </div>

        {/* Job Summary */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 mb-6">
          <h3 className="text-base font-bold text-slate-200">{job.title}</h3>
          <div className="flex items-center space-x-3 text-xs text-slate-400 mt-1">
            <span className="flex items-center space-x-1">
              <Building className="w-3.5 h-3.5 text-slate-500" />
              <span>{job.company}</span>
            </span>
            <span>•</span>
            <span className="flex items-center space-x-1">
              <MapPin className="w-3.5 h-3.5 text-cyan-400" />
              <span>{job.city}</span>
            </span>
          </div>
        </div>

        {/* Primary Action Button */}
        <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-indigo-900/30 via-slate-900 to-cyan-900/30 border border-indigo-500/20 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <span className="text-sm font-semibold text-slate-200 block">Step 1: Open Official Job Portal</span>
            <span className="text-xs text-slate-400">Opens Adzuna target URL directly in a new tab</span>
          </div>
          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary text-sm flex items-center space-x-2 shrink-0"
          >
            <span>Open Application Page</span>
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>

        {/* Optional AI Cover Note Generator */}
        <div className="border-t border-slate-800 pt-5">
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-semibold text-slate-200 flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>Step 2 (Optional): AI Cover Note Generator</span>
            </label>
            <button
              onClick={handleGenerateCoverNote}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-600/30 transition flex items-center space-x-1.5"
            >
              <Sparkles className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Generating...' : 'Generate Note'}</span>
            </button>
          </div>

          {coverNote ? (
            <div className="relative">
              <textarea
                rows={6}
                value={coverNote}
                onChange={(e) => setCoverNote(e.target.value)}
                className="w-full p-4 bg-slate-900/80 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-cyan-500 font-mono text-xs leading-relaxed"
              />
              <button
                onClick={handleCopy}
                className="absolute top-3 right-3 p-2 bg-slate-800/80 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-600 text-xs flex items-center space-x-1 transition"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                <span>{copied ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic bg-slate-900/40 p-4 rounded-xl border border-slate-800/60">
              Click 'Generate Note' to create a customized role-specific cover message to copy-paste into the job portal's application text box.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
