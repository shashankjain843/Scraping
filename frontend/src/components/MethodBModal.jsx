import React, { useState, useEffect } from 'react';
import { Mail, Send, Clock, FileText, X, AlertCircle, ShieldCheck, Upload } from 'lucide-react';
import { api } from '../api';


export default function MethodBModal({ job, user, onClose, onCreatedDraft }) {
  const [recipientEmail, setRecipientEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [resumeName, setResumeName] = useState(null);
  const [loading, setLoading] = useState(false);
  const [draftId, setDraftId] = useState(null);
  const [sendingNow, setSendingNow] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  useEffect(() => {
    if (job && user) {
      loadTemplateAndResume();
    }
  }, [job, user]);

  const loadTemplateAndResume = async () => {
    try {
      const templates = await api.getTemplates();
      const roleT = templates.find((t) => t.role_category === job.role_category);

      let subT = roleT?.subject_template || `Application for ${job.title} - ${job.company}`;
      let bodyT =
        roleT?.body_template ||
        `Dear Hiring Manager,\n\nI am writing to express my interest in the ${job.title} role at ${job.company} in ${job.city}.\n\nAttached is my resume for your review.\n\nSincerely,\n${user.full_name}`;

      // Render placeholders
      subT = subT
        .replace(/{{company}}/g, job.company)
        .replace(/{{job_title}}/g, job.title)
        .replace(/{{city}}/g, job.city)
        .replace(/{{user_name}}/g, user.full_name);

      bodyT = bodyT
        .replace(/{{company}}/g, job.company)
        .replace(/{{job_title}}/g, job.title)
        .replace(/{{city}}/g, job.city)
        .replace(/{{user_name}}/g, user.full_name)
        .replace(/{{user_email}}/g, user.email);

      setSubject(subT);
      setBody(bodyT);

      if (roleT?.has_resume) {
        setResumeName(roleT.resume_file_name || 'Resume Attached');
      } else {
        setResumeName(null);
      }
    } catch (err) {
      console.error('Error loading template', err);
    }
  };

  const handleCreateOrSaveDraft = async () => {
    if (!recipientEmail || !recipientEmail.includes('@')) {
      alert('Please enter a valid HR / Company email address manually.');
      return null;
    }

    setLoading(true);
    try {
      let d;
      if (!draftId) {
        d = await api.createDraft(job.id, recipientEmail);
        setDraftId(d.id);
      } else {
        d = await api.updateDraft(draftId, subject, body);
      }
      setStatusMsg({ type: 'success', text: 'Draft saved successfully!' });
      if (onCreatedDraft) onCreatedDraft();
      return d;
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
      return null;
    } finally {
      setLoading(false);
    }
  };

  const handleSendNow = async () => {
    if (!recipientEmail || !recipientEmail.includes('@')) {
      alert('Please enter a valid HR / Company email address manually.');
      return;
    }

    setSendingNow(true);
    setStatusMsg(null);

    try {
      let curDraftId = draftId;
      if (!curDraftId) {
        const d = await api.createDraft(job.id, recipientEmail);
        curDraftId = d.id;
        setDraftId(curDraftId);
      }
      await api.updateDraft(curDraftId, subject, body);

      const res = await api.sendDraftNow(curDraftId);
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
            <p className="text-xs text-slate-400">Draft, review, and send via your configured SMTP</p>
          </div>
        </div>

        {/* Compliance Notice */}
        <div className="mb-5 p-3 rounded-xl bg-cyan-950/40 border border-cyan-500/20 flex items-start space-x-3 text-xs text-cyan-300">
          <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Human-in-the-Loop Safeguard:</span> Emails are strictly generated as drafts from manually provided recipient addresses. Every outgoing email requires explicit human confirmation before sending.
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

        {/* Subject Line */}
        <div className="mb-4">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
            Subject Line
          </label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-medium"
          />
        </div>

        {/* Body Editor */}
        <div className="mb-4">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
            Email Body Preview & Editor
          </label>
          <textarea
            rows={8}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="w-full p-4 bg-slate-900/90 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-sans leading-relaxed"
          />
        </div>

        {/* Manual Resume Attachment File Picker */}
        <div className="mb-6 p-4 bg-slate-900/60 border border-slate-800 rounded-xl">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center justify-between">
            <span className="flex items-center space-x-2">
              <FileText className="w-4 h-4 text-emerald-400" />
              <span>Attach Resume (Manual per Draft)</span>
            </span>
            {resumeName && (
              <span className="text-xs font-semibold text-emerald-400">Attached: {resumeName}</span>
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
                  setResumeName(null);
                }}
                className="text-xs text-red-400 hover:underline"
              >
                Remove Attachment
              </button>
            </div>
          ) : (
            <label className="border border-dashed border-slate-700 hover:border-emerald-500/50 rounded-lg p-4 flex items-center justify-center space-x-2 cursor-pointer bg-slate-900/40 hover:bg-slate-900/80 transition">
              <Upload className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-semibold text-slate-300">Click to Select & Attach Resume PDF/DOCX</span>
              <input
                type="file"
                accept=".pdf,.docx,.doc"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files[0];
                  if (!file) return;
                  if (!recipientEmail) {
                    alert('Please enter recipient HR email first.');
                    return;
                  }
                  try {
                    let curId = draftId;
                    if (!curId) {
                      const d = await api.createDraft(job.id, recipientEmail);
                      curId = d.id;
                      setDraftId(curId);
                    }
                    const res = await api.uploadDraftResume(curId, file);
                    setResumeName(res.resume_name);
                  } catch (err) {
                    alert(err.message);
                  }
                }}
              />
            </label>
          )}
        </div>


        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            onClick={handleCreateOrSaveDraft}
            disabled={loading}
            className="w-full sm:w-auto btn-secondary text-sm flex items-center justify-center space-x-2"
          >
            <Clock className="w-4 h-4 text-amber-400" />
            <span>Save to Draft Queue</span>
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
