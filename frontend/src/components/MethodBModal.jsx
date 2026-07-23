import React, { useState } from 'react';
import { Mail, Send, Clock, FileText, X, AlertCircle, ShieldCheck, Upload } from 'lucide-react';
import { api } from '../api';

export default function MethodBModal({ job, user, onClose, onCreatedDraft }) {
  const [recipientEmail, setRecipientEmail] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [resumeName, setResumeName] = useState(null);
  const [loading, setLoading] = useState(false);
  const [draftId, setDraftId] = useState(null);
  const [sendingNow, setSendingNow] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setResumeName(file.name);
    }
  };

  const ensureDraftCreatedOrUpdated = async () => {
    if (!recipientEmail || !recipientEmail.includes('@')) {
      alert('Please enter a valid HR / Company email address manually.');
      return null;
    }

    if (!draftId && !selectedFile) {
      alert('Please upload your resume file first before generating the email draft.');
      return null;
    }

    if (!draftId) {
      const d = await api.createDraft(job.id, recipientEmail, selectedFile);
      setDraftId(d.id);
      setSubject(d.subject);
      setBody(d.body);
      if (d.resume_name) setResumeName(d.resume_name);
      return d;
    } else {
      const updated = await api.updateDraft(draftId, subject, body);
      return updated;
    }
  };

  const handleCreateOrSaveDraft = async () => {
    setLoading(true);
    setStatusMsg(null);
    try {
      const d = await ensureDraftCreatedOrUpdated();
      if (d) {
        setStatusMsg({ type: 'success', text: 'Draft generated and saved to queue successfully!' });
        if (onCreatedDraft) onCreatedDraft();
      }
      return d;
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
      return null;
    } finally {
      setLoading(false);
    }
  };

  const handleSendNow = async () => {
    setSendingNow(true);
    setStatusMsg(null);

    try {
      const d = await ensureDraftCreatedOrUpdated();
      if (!d) return;

      const res = await api.sendDraftNow(d.id);
      setStatusMsg({ type: 'success', text: res.message || 'Email sent successfully via SMTP!' });
      if (onCreatedDraft) onCreatedDraft();
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setStatusMsg({ type: 'error', text: 'Failed to send: ' + err.message });
    } finally {
      setSendingNow(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="glass-panel w-full max-w-3xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-cyan-600/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <Mail className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">Method B: Direct Email Application</h2>
            <p className="text-xs text-slate-400">Upload resume, generate personalized draft, review & send via SMTP</p>
          </div>
        </div>

        {/* Compliance Notice */}
        <div className="mb-5 p-3 rounded-xl bg-cyan-950/40 border border-cyan-500/20 flex items-start space-x-3 text-xs text-cyan-300">
          <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Human-in-the-Loop Safeguard:</span> Upload your resume and enter recipient address. Draft is generated after reading your resume. Review and edit before sending.
          </div>
        </div>

        {statusMsg && (
          <div
            className={`p-3 rounded-xl mb-4 text-xs font-semibold flex items-center space-x-2 ${
              statusMsg.type === 'success'
                ? 'bg-emerald-950/60 border border-emerald-500/30 text-emerald-300'
                : 'bg-red-950/60 border border-red-500/30 text-red-300'
            }`}
          >
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{statusMsg.text}</span>
          </div>
        )}

        {/* Manual HR Email Input */}
        <div className="mb-4">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
            Recipient HR / Company Email <span className="text-red-400">*</span> (Manual Entry)
          </label>
          <input
            type="email"
            placeholder="e.g. hr@company.com or careers@company.com"
            value={recipientEmail}
            onChange={(e) => setRecipientEmail(e.target.value)}
            className="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Mandatory Resume Attachment Upload FIRST */}
        <div className="mb-6 p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center justify-between">
            <span className="flex items-center space-x-2">
              <FileText className="w-4 h-4 text-emerald-400" />
              <span>Step 1: Upload Resume (PDF / DOCX) <span className="text-red-400">*</span></span>
            </span>
            {resumeName && (
              <span className="text-xs font-semibold text-emerald-400">Selected: {resumeName}</span>
            )}
          </label>

          {resumeName ? (
            <div className="flex items-center justify-between p-3 bg-slate-900 border border-emerald-500/30 rounded-lg">
              <span className="text-xs font-medium text-slate-200">{resumeName}</span>
              <button
                onClick={async () => {
                  if (draftId) {
                    await api.removeDraftResume(draftId);
                  }
                  setSelectedFile(null);
                  setResumeName(null);
                  setDraftId(null);
                  setSubject('');
                  setBody('');
                }}
                className="text-xs text-red-400 hover:underline"
              >
                Change Resume
              </button>
            </div>
          ) : (
            <label className="border border-dashed border-slate-700 hover:border-emerald-500/50 rounded-lg p-4 flex items-center justify-center space-x-2 cursor-pointer bg-slate-900/40 hover:bg-slate-900/80 transition">
              <Upload className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-semibold text-slate-300">Click to Select Resume PDF/DOCX (Parsed for Draft)</span>
              <input
                type="file"
                accept=".pdf,.docx,.doc"
                className="hidden"
                onChange={handleFileSelect}
              />
            </label>
          )}
        </div>

        {/* Step 2: Generated Email Subject & Body Preview */}
        {draftId || (selectedFile && recipientEmail) ? (
          <>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Subject Line (Auto-generated & Editable)
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Click 'Generate & Save Draft' to populate"
                className="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-medium"
              />
            </div>

            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Email Body Preview & Editor (Parsed Candidate Sign-Off)
              </label>
              <textarea
                rows={8}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Click 'Generate & Save Draft' to populate"
                className="w-full p-4 bg-slate-900/90 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-sans leading-relaxed"
              />
            </div>
          </>
        ) : null}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            onClick={handleCreateOrSaveDraft}
            disabled={loading}
            className="w-full sm:w-auto btn-secondary text-sm flex items-center justify-center space-x-2"
          >
            <Clock className="w-4 h-4 text-amber-400" />
            <span>{draftId ? 'Save Draft Edits' : 'Generate & Save to Draft Queue'}</span>
          </button>

          <button
            onClick={handleSendNow}
            disabled={sendingNow}
            className="w-full sm:w-auto btn-primary text-sm flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            <Send className={`w-4 h-4 ${sendingNow ? 'animate-bounce' : ''}`} />
            <span>{sendingNow ? 'Sending Email...' : 'Send Email Now'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
