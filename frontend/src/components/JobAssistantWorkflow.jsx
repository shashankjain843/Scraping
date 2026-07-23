import React, { useState } from 'react';
import { Search, Sparkles, Send, Edit, Trash2, FileText, CheckCircle, AlertCircle, RefreshCw, Mail, ExternalLink, ShieldCheck, MapPin, Briefcase } from 'lucide-react';
import { api } from '../api';

export default function JobAssistantWorkflow() {
  const [role, setRole] = useState('Data Analyst');
  const [location, setLocation] = useState('Jaipur');
  const [customRole, setCustomRole] = useState('');
  const [customLocation, setCustomLocation] = useState('');

  const [loading, setLoading] = useState(false);
  const [searchDone, setSearchDone] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [manualJobs, setManualJobs] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);

  const [editingId, setEditingId] = useState(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');

  const [sendingId, setSendingId] = useState(null);
  const [batchSending, setBatchSending] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  const rolesList = ['Data Analyst', 'Data Scientist', 'Frontend Developer', 'Python Developer', 'Backend Engineer', 'Full Stack Developer'];
  const locationsList = ['Jaipur', 'Noida', 'Gurgaon', 'Delhi', 'Pune', 'Hyderabad', 'Bangalore', 'Ahmedabad', 'Remote'];

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    const finalRole = role === 'Other' ? customRole : role;
    const finalLocation = location === 'Other' ? customLocation : location;

    if (!finalRole || !finalLocation) {
      alert('Please select or specify both Role and Location.');
      return;
    }

    setLoading(true);
    setStatusMsg(null);
    try {
      const res = await api.searchAssistant(finalRole, finalLocation);
      setDrafts(res.drafts || []);
      setManualJobs(res.manual_followup_jobs || []);
      setSearchDone(true);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedIds(drafts.map((d) => d.id));
    } else {
      setSelectedIds([]);
    }
  };

  const toggleSelect = (id) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((item) => item !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleSendSingle = async (draftId) => {
    setSendingId(draftId);
    setStatusMsg(null);
    try {
      if (editingId === draftId) {
        await api.updateDraft(draftId, editSubject, editBody);
        setEditingId(null);
      }
      const res = await api.sendDraftNow(draftId);
      setStatusMsg({ type: 'success', text: res.message || 'Email successfully sent via SMTP!' });
      setDrafts(drafts.filter((d) => d.id !== draftId));
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setSendingId(null);
    }
  };

  const handleSendSelected = async () => {
    if (selectedIds.length === 0) {
      alert('Please actively select at least one draft to send.');
      return;
    }

    setBatchSending(true);
    setStatusMsg(null);
    try {
      const res = await api.approveBatchDrafts(selectedIds, 120);
      setStatusMsg({ type: 'success', text: res.message || `Authorized ${selectedIds.length} email sends with courteous pacing.` });
      setDrafts(drafts.filter((d) => !selectedIds.includes(d.id)));
      setSelectedIds([]);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setBatchSending(false);
    }
  };

  const handleSkip = (draftId) => {
    setDrafts(drafts.filter((d) => d.id !== draftId));
    setSelectedIds(selectedIds.filter((id) => id !== draftId));
  };

  const startInlineEdit = (draft) => {
    setEditingId(draft.id);
    setEditSubject(draft.subject);
    setEditBody(draft.body);
  };

  const saveInlineEdit = async (draftId) => {
    try {
      await api.updateDraft(draftId, editSubject, editBody);
      setDrafts(drafts.map((d) => (d.id === draftId ? { ...d, subject: editSubject, body: editBody } : d)));
      setEditingId(null);
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Input Header & Form */}
      <div className="glass-panel p-6">
        <div className="flex items-center space-x-3 mb-4">
          <div className="p-2.5 bg-indigo-500/20 border border-indigo-500/30 rounded-xl text-indigo-400">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">Semi-Automated Job Application Assistant</h2>
            <p className="text-xs text-slate-400">Select Target Role & Location. Backend extracts visible HR emails via regex, attaches stored resume, and prepares review drafts.</p>
          </div>
        </div>

        <form onSubmit={handleSearch} className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Step 1: Role Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center space-x-1">
              <Briefcase className="w-3.5 h-3.5 text-indigo-400" />
              <span>Target Role</span>
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
            >
              {rolesList.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
              <option value="Other">Other (Custom Role)</option>
            </select>

            {role === 'Other' && (
              <input
                type="text"
                placeholder="Enter custom role..."
                value={customRole}
                onChange={(e) => setCustomRole(e.target.value)}
                className="mt-2 w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
              />
            )}
          </div>

          {/* Step 1: Location Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5 flex items-center space-x-1">
              <MapPin className="w-3.5 h-3.5 text-cyan-400" />
              <span>Target Location</span>
            </label>
            <select
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200"
            >
              {locationsList.map((loc) => (
                <option key={loc} value={loc}>
                  {loc}
                </option>
              ))}
              <option value="Other">Other (Custom City)</option>
            </select>

            {location === 'Other' && (
              <input
                type="text"
                placeholder="Enter custom location..."
                value={customLocation}
                onChange={(e) => setCustomLocation(e.target.value)}
                className="mt-2 w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200"
              />
            )}
          </div>

          {/* Submit Action */}
          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary text-xs py-2.5 px-4 flex items-center justify-center space-x-2"
            >
              <Search className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Searching & Extracting...' : 'Find Jobs & Draft Emails'}</span>
            </button>
          </div>
        </form>
      </div>

      {statusMsg && (
        <div
          className={`p-4 rounded-xl text-xs font-semibold flex items-center space-x-2 ${
            statusMsg.type === 'success'
              ? 'bg-emerald-950/60 border border-emerald-500/30 text-emerald-300'
              : 'bg-red-950/60 border border-red-500/30 text-red-300'
          }`}
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Step 2 & 3: Results Grouping */}
      {searchDone && (
        <div className="space-y-6">
          {/* Section A: Extracted Email Auto-Drafts */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-bold text-slate-100">Review & Confirm Application Drafts</h3>
                <span className="badge-indigo">{drafts.length} Ready for Review</span>
              </div>

              {drafts.length > 0 && (
                <button
                  onClick={handleSendSelected}
                  disabled={batchSending || selectedIds.length === 0}
                  className="btn-primary text-xs flex items-center space-x-2 py-2 px-4 disabled:opacity-40"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Send Selected ({selectedIds.length})</span>
                </button>
              )}
            </div>

            {drafts.length === 0 ? (
              <div className="glass-panel p-8 text-center text-xs text-slate-400">
                No email address regex matches in description text for these specific posts. Check the manual follow-up list below.
              </div>
            ) : (
              <div className="glass-panel overflow-hidden">
                <div className="p-3.5 bg-slate-900/60 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      onChange={handleSelectAll}
                      checked={selectedIds.length === drafts.length && drafts.length > 0}
                      className="rounded border-slate-700 bg-slate-900 text-indigo-500 w-4 h-4"
                    />
                    <span>Select All ({selectedIds.length} checked)</span>
                  </label>
                  <span>Human Confirmation Required before sending</span>
                </div>

                <div className="divide-y divide-slate-800">
                  {drafts.map((d) => {
                    const isSelected = selectedIds.includes(d.id);
                    const isEditing = editingId === d.id;

                    return (
                      <div key={d.id} className={`p-6 transition ${isSelected ? 'bg-indigo-950/20' : 'hover:bg-slate-900/40'}`}>
                        <div className="flex items-start space-x-4">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(d.id)}
                            className="mt-1.5 rounded border-slate-700 bg-slate-900 text-indigo-500 w-4 h-4 cursor-pointer"
                          />

                          <div className="flex-1 min-w-0">
                            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                              <div className="flex items-center space-x-3">
                                <span className="font-bold text-base text-slate-100">{d.company_name}</span>
                                <span className="text-sm text-slate-400">• {d.job_title}</span>
                              </div>
                              <span className="text-xs font-mono text-cyan-300 bg-slate-900 px-3 py-1 rounded-full border border-slate-800">
                                Extracted HR Email: <strong>{d.recipient_email}</strong>
                              </span>
                            </div>

                            {/* Inline Draft Editor */}
                            {isEditing ? (
                              <div className="my-3 space-y-3 bg-slate-900/90 p-4 rounded-xl border border-indigo-500/40">
                                <div>
                                  <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Subject</label>
                                  <input
                                    type="text"
                                    value={editSubject}
                                    onChange={(e) => setEditSubject(e.target.value)}
                                    className="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200"
                                  />
                                </div>
                                <div>
                                  <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Body Text</label>
                                  <textarea
                                    rows={5}
                                    value={editBody}
                                    onChange={(e) => setEditBody(e.target.value)}
                                    className="w-full p-3 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 leading-relaxed font-sans"
                                  />
                                </div>
                                <div className="flex justify-end space-x-2">
                                  <button onClick={() => setEditingId(null)} className="btn-secondary text-xs py-1 px-3">
                                    Cancel
                                  </button>
                                  <button onClick={() => saveInlineEdit(d.id)} className="btn-primary text-xs py-1 px-3">
                                    Save Edits
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="my-2 p-3 bg-slate-900/60 rounded-xl border border-slate-800/80">
                                <div className="text-xs font-semibold text-slate-300 mb-1">Subject: "{d.subject}"</div>
                                <p className="text-xs text-slate-400 whitespace-pre-line leading-relaxed font-sans">{d.body}</p>
                              </div>
                            )}

                            {/* Footer info & Buttons (Edit, Skip, Send) */}
                            <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-800/50">
                              <div className="flex items-center space-x-2 text-xs text-slate-400">
                                <FileText className="w-4 h-4 text-emerald-400" />
                                <span>Attached Profile Resume:</span>
                                <span className="font-semibold text-emerald-300">{d.resume_name || 'Stored Resume (PDF)'}</span>
                              </div>

                              <div className="flex items-center space-x-2">
                                <button
                                  onClick={() => startInlineEdit(d)}
                                  className="btn-secondary text-xs py-1.5 px-3 flex items-center space-x-1"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                  <span>Edit</span>
                                </button>

                                <button
                                  onClick={() => handleSkip(d.id)}
                                  className="p-1.5 text-slate-400 hover:text-slate-200 bg-slate-800 rounded-lg text-xs px-2.5"
                                >
                                  Skip
                                </button>

                                <button
                                  onClick={() => handleSendSingle(d.id)}
                                  disabled={sendingId === d.id}
                                  className="btn-primary text-xs py-1.5 px-4 flex items-center space-x-1.5 shadow-lg shadow-indigo-500/20"
                                >
                                  <Send className={`w-3.5 h-3.5 ${sendingId === d.id ? 'animate-bounce' : ''}`} />
                                  <span>{sendingId === d.id ? 'Sending...' : 'Send'}</span>
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Section B: Manual Follow-Up Jobs (no_email_found) */}
          {manualJobs.length > 0 && (
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <h3 className="text-lg font-bold text-slate-100">Manual Follow-up List</h3>
                <span className="badge-amber">{manualJobs.length} No Email Found</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {manualJobs.map((j) => (
                  <div key={j.id} className="glass-panel p-5 space-y-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-bold text-slate-200 text-sm">{j.title}</h4>
                        <p className="text-xs text-slate-400">{j.company} • {j.location}</p>
                      </div>
                      <span className="text-[11px] font-semibold text-amber-400 bg-amber-950/60 border border-amber-500/30 px-2 py-0.5 rounded-full">
                        no_email_found
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-3">{j.description}</p>

                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                      <span className="text-[11px] text-slate-500">Apply via Official Portal</span>
                      <a
                        href={j.apply_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-primary text-xs py-1.5 px-3 flex items-center space-x-1.5"
                      >
                        <span>Official Link</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
