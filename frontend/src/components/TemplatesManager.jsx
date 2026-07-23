import React, { useState, useEffect } from 'react';
import { FileText, Upload, Trash2, Save, Check, AlertCircle, Sparkles, Edit2, Eye } from 'lucide-react';
import { api } from '../api';

export default function TemplatesManager() {
  const [activeRole, setActiveRole] = useState('data_analyst');
  const [templates, setTemplates] = useState([]);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [resumeInfo, setResumeInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  useEffect(() => {
    fetchTemplates();
  }, []);

  useEffect(() => {
    if (templates.length > 0) {
      const cur = templates.find((t) => t.role_category === activeRole);
      if (cur) {
        setSubject(cur.subject_template || '');
        setBody(cur.body_template || '');
        setResumeInfo(cur.has_resume ? cur.resume_file_name || 'Attached' : null);
      } else {
        setSubject('');
        setBody('');
        setResumeInfo(null);
      }
    }
    setIsEditing(false);
  }, [activeRole, templates]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const data = await api.getTemplates();
      setTemplates(data);
    } catch (err) {
      console.error('Error fetching templates', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveEdits = async () => {
    setStatusMsg(null);
    try {
      await api.updateTemplate(activeRole, subject, body);
      setStatusMsg({ type: 'success', text: 'Template edits saved!' });
      setIsEditing(false);
      fetchTemplates();
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setStatusMsg(null);
    try {
      const res = await api.uploadResume(activeRole, file);
      setStatusMsg({ type: 'success', text: res.message || 'Resume uploaded & template auto-generated!' });
      // Update subject/body from auto-generated response
      if (res.subject_template) setSubject(res.subject_template);
      if (res.body_template) setBody(res.body_template);
      fetchTemplates();
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleRemoveResume = async () => {
    if (!confirm('Remove this resume? The auto-generated template will remain editable.')) return;
    try {
      await api.removeResume(activeRole);
      setStatusMsg({ type: 'success', text: 'Resume removed.' });
      fetchTemplates();
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    }
  };

  const roleLabel = activeRole === 'data_analyst' ? 'Data Analyst' : 'Data Scientist';
  const roleColor = activeRole === 'data_analyst' ? 'indigo' : 'cyan';
  const hasTemplate = subject.trim().length > 0;

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Role-Based Email Templates</h2>
          <p className="text-xs text-slate-400 mt-1">
            Upload your resume for each role — the system will auto-generate a professional email template from it.
            Resume is automatically attached to every draft for that role.
          </p>
        </div>

        {/* Role Tab Switcher */}
        <div className="flex bg-slate-900/80 p-1 rounded-xl border border-slate-800 self-start">
          <button
            onClick={() => setActiveRole('data_analyst')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
              activeRole === 'data_analyst'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Data Analyst
          </button>
          <button
            onClick={() => setActiveRole('data_scientist')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
              activeRole === 'data_scientist'
                ? 'bg-cyan-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Data Scientist
          </button>
        </div>
      </div>

      {/* Status Message */}
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* LEFT: Resume Upload Card */}
        <div className="space-y-5">
          <div className="glass-panel p-6">
            <h3 className="text-base font-bold text-slate-200 mb-1 flex items-center space-x-2">
              <FileText className={`w-5 h-5 text-${roleColor}-400`} />
              <span>{roleLabel} Resume</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Upload once — auto-attaches to every {roleLabel} draft and personalizes your email signature.
            </p>

            {resumeInfo ? (
              <div className="p-4 bg-slate-900/80 border border-emerald-500/30 rounded-xl">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2 overflow-hidden">
                    <FileText className="w-5 h-5 text-emerald-400 shrink-0" />
                    <span className="text-xs font-semibold text-slate-200 truncate">{resumeInfo}</span>
                  </div>
                  <button
                    onClick={handleRemoveResume}
                    className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition"
                    title="Remove resume"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {/* Replace with different resume */}
                <label className="w-full flex items-center justify-center space-x-2 text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer border border-dashed border-slate-700 hover:border-slate-500 rounded-lg py-2 transition">
                  <Upload className="w-3.5 h-3.5" />
                  <span>{uploading ? 'Uploading...' : 'Replace Resume'}</span>
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc"
                    onChange={handleFileUpload}
                    className="hidden"
                    disabled={uploading}
                  />
                </label>
              </div>
            ) : (
              <label className={`border-2 border-dashed border-slate-700 hover:border-${roleColor}-500/50 rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer bg-slate-900/30 hover:bg-slate-900/60 transition`}>
                <Upload className={`w-10 h-10 text-${roleColor}-400 mb-3`} />
                <span className="text-sm font-semibold text-slate-300">
                  {uploading ? 'Uploading & Generating...' : 'Click to Upload Resume'}
                </span>
                <span className="text-[11px] text-slate-500 mt-1">PDF, DOCX, DOC supported</span>
                <div className={`mt-3 flex items-center space-x-1.5 text-[11px] text-${roleColor}-400 font-medium`}>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Template auto-generates on upload</span>
                </div>
                <input
                  type="file"
                  accept=".pdf,.docx,.doc"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploading}
                />
              </label>
            )}
          </div>

          {/* Placeholders reference (compact) */}
          {hasTemplate && (
            <div className="glass-panel p-4">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Auto-filled Placeholders</p>
              <div className="space-y-1.5 text-[11px]">
                {[
                  ['{{company}}', 'Company Name'],
                  ['{{job_title}}', 'Job Title'],
                  ['{{city}}', 'City'],
                  ['{{user_name}}', 'Your Name'],
                  ['{{user_email}}', 'Your Email'],
                ].map(([tag, desc]) => (
                  <div key={tag} className="flex items-center justify-between px-2 py-1 rounded bg-slate-900/60 border border-slate-800">
                    <code className="text-indigo-300 font-bold">{tag}</code>
                    <span className="text-slate-500">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Generated Template Preview */}
        <div className="lg:col-span-2 glass-panel p-6">
          {!hasTemplate ? (
            <div className="h-full flex flex-col items-center justify-center text-center py-16">
              <Sparkles className="w-12 h-12 text-slate-600 mb-4" />
              <h3 className="text-base font-bold text-slate-400 mb-2">No Template Yet</h3>
              <p className="text-xs text-slate-500 max-w-xs">
                Upload your {roleLabel} resume on the left — a professional email template will be automatically generated and shown here.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <Sparkles className={`w-4 h-4 text-${roleColor}-400`} />
                  <span className="text-sm font-bold text-slate-200">Auto-Generated Template</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full bg-${roleColor}-950/60 border border-${roleColor}-500/30 text-${roleColor}-300 font-semibold`}>
                    {roleLabel}
                  </span>
                </div>
                <button
                  onClick={() => setIsEditing(!isEditing)}
                  className="flex items-center space-x-1.5 text-xs font-semibold text-slate-400 hover:text-slate-200 transition"
                >
                  {isEditing ? <Eye className="w-3.5 h-3.5" /> : <Edit2 className="w-3.5 h-3.5" />}
                  <span>{isEditing ? 'Preview' : 'Edit'}</span>
                </button>
              </div>

              {/* Subject */}
              <div className="mb-4">
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                  Subject
                </label>
                {isEditing ? (
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-900/80 border border-indigo-500/40 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-400"
                  />
                ) : (
                  <div className="px-4 py-2.5 bg-slate-900/60 border border-slate-800 rounded-xl text-sm text-slate-200 font-medium">
                    {subject}
                  </div>
                )}
              </div>

              {/* Body */}
              <div className="mb-5">
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1.5">
                  Email Body
                </label>
                {isEditing ? (
                  <textarea
                    rows={14}
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    className="w-full p-4 bg-slate-900/80 border border-indigo-500/40 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-400 font-sans leading-relaxed"
                  />
                ) : (
                  <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-sm text-slate-300 whitespace-pre-wrap leading-relaxed font-sans">
                    {body}
                  </div>
                )}
              </div>

              {/* Save button only shown in edit mode */}
              {isEditing && (
                <div className="flex justify-end space-x-3">
                  <button
                    onClick={() => { setIsEditing(false); fetchTemplates(); }}
                    className="btn-secondary text-xs py-2 px-4"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveEdits}
                    className="btn-primary text-xs py-2 px-4 flex items-center space-x-2"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>Save Edits</span>
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
