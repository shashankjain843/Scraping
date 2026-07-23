import React, { useState, useEffect } from 'react';
import { FileText, Upload, Trash2, Save, Check, AlertCircle, FileCode, Tag } from 'lucide-react';
import { api } from '../api';

export default function TemplatesManager() {
  const [activeRole, setActiveRole] = useState('data_analyst');
  const [templates, setTemplates] = useState([]);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [resumeInfo, setResumeInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
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

  const handleSaveTemplate = async () => {
    setStatusMsg(null);
    try {
      const updated = await api.updateTemplate(activeRole, subject, body);
      setStatusMsg({ type: 'success', text: `Saved ${activeRole.replace('_', ' ')} template!` });
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
      setStatusMsg({ type: 'success', text: res.message });
      fetchTemplates();
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveResume = async () => {
    if (!confirm('Are you sure you want to remove this resume?')) return;
    try {
      await api.removeResume(activeRole);
      setStatusMsg({ type: 'success', text: 'Resume removed.' });
      fetchTemplates();
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    }
  };

  const tags = [
    { tag: '{{company}}', desc: 'Company Name' },
    { tag: '{{job_title}}', desc: 'Job Title' },
    { tag: '{{city}}', desc: 'Target City' },
    { tag: '{{user_name}}', desc: 'Your Full Name' },
    { tag: '{{user_email}}', desc: 'Your Reply Email' },
  ];

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Role-Based Email Templates</h2>
          <p className="text-xs text-slate-400">Configure pre-filled email subject and body copy for Data Analyst and Data Scientist roles. (Resume files are manually attached per draft on the draft screen before sending).</p>
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
            Data Analyst Template
          </button>
          <button
            onClick={() => setActiveRole('data_scientist')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
              activeRole === 'data_scientist'
                ? 'bg-cyan-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Data Scientist Template
          </button>
        </div>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Template Form (2 Cols) */}
        <div className="lg:col-span-2 glass-panel p-6">
          <div className="mb-4">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Subject Line Template
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-medium"
            />
          </div>

          <div className="mb-4">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Email Body Template
            </label>
            <textarea
              rows={12}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full p-4 bg-slate-900/90 border border-slate-700/60 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-indigo-500 font-sans leading-relaxed"
            />
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSaveTemplate}
              className="btn-primary text-sm flex items-center space-x-2"
            >
              <Save className="w-4 h-4" />
              <span>Save {activeRole === 'data_analyst' ? 'Data Analyst' : 'Data Scientist'} Template</span>
            </button>
          </div>
        </div>

        {/* Sidebar: Resume Manager & Dynamic Tag Guide */}
        <div className="space-y-6">
          {/* Resume Upload Box */}
          <div className="glass-panel p-6">
            <h3 className="text-base font-bold text-slate-200 mb-1 flex items-center space-x-2">
              <FileText className="w-5 h-5 text-cyan-400" />
              <span>Resume Attachment ({activeRole === 'data_analyst' ? 'DA' : 'DS'})</span>
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Upload the dedicated PDF/DOCX resume for this role. It will automatically attach to draft emails of this type.
            </p>

            {resumeInfo ? (
              <div className="p-4 bg-slate-900/80 border border-emerald-500/30 rounded-xl flex items-center justify-between">
                <div className="flex items-center space-x-2 overflow-hidden">
                  <FileText className="w-5 h-5 text-emerald-400 shrink-0" />
                  <span className="text-xs font-semibold text-slate-200 truncate">{resumeInfo}</span>
                </div>
                <button
                  onClick={handleRemoveResume}
                  className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <label className="border-2 border-dashed border-slate-700 hover:border-cyan-500/50 rounded-xl p-6 flex flex-col items-center justify-center cursor-pointer bg-slate-900/30 hover:bg-slate-900/60 transition">
                <Upload className="w-8 h-8 text-cyan-400 mb-2" />
                <span className="text-xs font-semibold text-slate-300">
                  {uploading ? 'Uploading...' : 'Click to Upload Resume'}
                </span>
                <span className="text-[10px] text-slate-500 mt-1">Supported: PDF, DOCX, DOC</span>
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

          {/* Placeholders Guide */}
          <div className="glass-panel p-6">
            <h3 className="text-base font-bold text-slate-200 mb-3 flex items-center space-x-2">
              <Tag className="w-4 h-4 text-indigo-400" />
              <span>Available Placeholders</span>
            </h3>
            <div className="space-y-2 text-xs">
              {tags.map((t) => (
                <div
                  key={t.tag}
                  onClick={() => setBody((prev) => prev + ' ' + t.tag)}
                  className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-indigo-500/40 cursor-pointer flex items-center justify-between transition"
                >
                  <code className="text-indigo-300 font-bold">{t.tag}</code>
                  <span className="text-slate-400 text-[11px]">{t.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
