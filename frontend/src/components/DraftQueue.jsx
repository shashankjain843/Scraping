import React, { useState, useEffect } from 'react';
import { Send, Trash2, Edit, AlertCircle, CheckCircle, RefreshCw, Mail, FileText, CheckSquare, Square, Building, MapPin, Sparkles, Save, ShieldCheck } from 'lucide-react';
import { api } from '../api';

export default function DraftQueue() {
  const [drafts, setDrafts] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingId, setSendingId] = useState(null);
  const [batchSending, setBatchSending] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  useEffect(() => {
    fetchDrafts();
  }, []);

  const fetchDrafts = async () => {
    setLoading(true);
    try {
      const data = await api.getDrafts();
      setDrafts(data);
    } catch (err) {
      console.error('Error fetching pending approvals', err);
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

  const handleApproveSingle = async (draftId) => {
    setSendingId(draftId);
    setStatusMsg(null);
    try {
      // Save inline edits if editing this draft
      if (editingId === draftId) {
        await api.updateDraft(draftId, editSubject, editBody);
        setEditingId(null);
      }

      const res = await api.sendDraftNow(draftId);
      setStatusMsg({ type: 'success', text: res.message || 'Email approved and sent via SMTP!' });
      fetchDrafts();
    } catch (err) {
      setStatusMsg({ type: 'error', text: 'Approval failed: ' + err.message });
    } finally {
      setSendingId(null);
    }
  };

  const handleApproveBatch = async () => {
    if (selectedIds.length === 0) {
      alert('Please actively select at least one draft to approve and send.');
      return;
    }

    setBatchSending(true);
    setStatusMsg(null);
    try {
      const res = await api.approveBatchDrafts(selectedIds, 120); // 2 minute courteous pacing
      setStatusMsg({
        type: 'success',
        text: res.message || `Authorized ${selectedIds.length} email sends with 2-minute courteous pacing.`,
      });
      setSelectedIds([]);
      fetchDrafts();
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setBatchSending(false);
    }
  };

  const handleDelete = async (draftId) => {
    if (!confirm('Are you sure you want to remove this draft?')) return;
    try {
      await api.deleteDraft(draftId);
      fetchDrafts();
    } catch (err) {
      alert(err.message);
    }
  };

  const startInlineEdit = (draft) => {
    setEditingId(draft.id);
    setEditSubject(draft.subject);
    setEditBody(draft.body);
  };

  const saveInlineEdit = async (draftId) => {
    try {
      await api.updateDraft(draftId, editSubject, editBody);
      setEditingId(null);
      fetchDrafts();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-100 flex items-center space-x-2">
            <span>Pending Approvals Inbox</span>
            <span className="badge-amber text-xs">{drafts.length} Pending</span>
          </h2>
          <p className="text-xs text-slate-400">
            Review pre-filled application drafts, edit subject/body inline, attach resumes manually, and click 'Approve & Send'.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchDrafts}
            className="p-2.5 text-slate-400 hover:text-slate-200 bg-slate-900 rounded-xl border border-slate-800 transition"
            title="Refresh Pending Approvals"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={handleApproveBatch}
            disabled={batchSending || selectedIds.length === 0}
            className="btn-primary text-sm flex items-center space-x-2 py-2.5 px-4 disabled:opacity-40"
          >
            <Send className={`w-4 h-4 ${batchSending ? 'animate-bounce' : ''}`} />
            <span>Approve & Send Selected ({selectedIds.length})</span>
          </button>
        </div>
      </div>

      {/* Compliance Note */}
      <div className="mb-6 p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start space-x-3 text-xs text-slate-300">
        <ShieldCheck className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-slate-100">1-Click Human Approval Guarantee:</span> Outgoing emails are never auto-sent by background schedulers. Each email requires your active click ("Approve & Send"). Checked batches send with 2-minute courteous pacing to protect your outbox.
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

      {drafts.length === 0 ? (
        <div className="glass-panel p-16 text-center">
          <Mail className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-300">Pending Approvals Inbox Empty</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Browse jobs in the Job Feed and click 'Apply via Email (Draft)' to manually enter an HR email and stage an application draft for review.
          </p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden">
          {/* Inbox Table Header Bar */}
          <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
            <label className="flex items-center space-x-2 text-xs font-semibold text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                onChange={handleSelectAll}
                checked={selectedIds.length === drafts.length && drafts.length > 0}
                className="rounded border-slate-700 bg-slate-900 text-indigo-500 w-4 h-4"
              />
              <span>Select All ({selectedIds.length} checked by user)</span>
            </label>
            <span className="text-xs text-slate-400">{drafts.length} pending approval drafts</span>
          </div>

          {/* Pending Draft Rows */}
          <div className="divide-y divide-slate-800/80">
            {drafts.map((d) => {
              const isSelected = selectedIds.includes(d.id);
              const isEditing = editingId === d.id;

              return (
                <div key={d.id} className={`p-6 transition ${isSelected ? 'bg-indigo-950/20' : 'hover:bg-slate-900/40'}`}>
                  <div className="flex items-start space-x-4">
                    {/* Active Checkbox (Unchecked by default) */}
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(d.id)}
                      className="mt-1.5 rounded border-slate-700 bg-slate-900 text-indigo-500 w-4 h-4 cursor-pointer"
                    />

                    <div className="flex-1 min-w-0">
                      {/* Company, Title, Role Badges */}
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                        <div className="flex items-center space-x-3">
                          <span className="font-bold text-base text-slate-100">{d.company_name}</span>
                          <span className="text-sm text-slate-400 font-medium">• {d.job_title}</span>
                          {d.role_category === 'data_analyst' ? (
                            <span className="badge-indigo">Data Analyst</span>
                          ) : d.role_category === 'data_scientist' ? (
                            <span className="badge-cyan">Data Scientist</span>
                          ) : (
                            <span className="badge-amber bg-amber-950/60 border-amber-500/40 text-amber-300">⚠️ Unmatched Title (Review Required)</span>
                          )}
                        </div>

                        <span className="text-xs font-mono text-cyan-300 bg-slate-900 px-3 py-1 rounded-full border border-slate-800">
                          Recipient HR: <strong>{d.recipient_email}</strong>
                        </span>
                      </div>

                      {/* Unmatched role banner */}
                      {(d.is_unmatched || d.role_category === 'unmatched') && (
                        <div className="mb-2 p-2 bg-amber-950/30 border border-amber-500/30 rounded-lg text-xs text-amber-300 font-medium flex items-center space-x-1.5">
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                          <span>Unmatched Job Title: System did not auto-assign a template to prevent wrong role match. Please edit the draft text below.</span>
                        </div>
                      )}


                      {/* Inline Editable Subject & Body */}
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
                            <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Body Preview</label>
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
                            <button onClick={() => saveInlineEdit(d.id)} className="btn-primary text-xs py-1 px-3 flex items-center space-x-1">
                              <Save className="w-3.5 h-3.5" />
                              <span>Save Inline Edits</span>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="my-2 p-3 bg-slate-900/60 rounded-xl border border-slate-800/80">
                          <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-1">
                            <span>Subject: "{d.subject}"</span>
                            <button
                              onClick={() => startInlineEdit(d)}
                              className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 font-medium"
                            >
                              <Edit className="w-3 h-3" />
                              <span>Edit Inline</span>
                            </button>
                          </div>
                          <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed font-sans">{d.body}</p>
                        </div>
                      )}

                      {/* Auto-Attached Resume Badge (read-only — set from role template) */}
                      <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-800/50">
                        <div className="flex items-center space-x-2 text-xs">
                          <FileText className="w-4 h-4 text-emerald-400" />
                          <span className="text-slate-400 font-medium">Resume:</span>
                          {d.resume_name ? (
                            <div className="flex items-center space-x-1.5 bg-emerald-950/40 border border-emerald-500/30 px-2.5 py-1 rounded-lg">
                              <span className="text-emerald-300 font-semibold">{d.resume_name}</span>
                              <span className="text-[10px] text-emerald-600">auto-attached</span>
                            </div>
                          ) : (
                            <span className="text-slate-500 italic text-[11px]">
                              No resume — upload one in the Templates tab for this role
                            </span>
                          )}
                        </div>

                        {/* Action Buttons: 1-Click Approve & Send */}
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => handleDelete(d.id)}
                            className="p-2 text-slate-400 hover:text-red-400 bg-slate-800/60 hover:bg-slate-800 rounded-xl transition"
                            title="Delete Draft"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>

                          <button
                            onClick={() => handleApproveSingle(d.id)}
                            disabled={sendingId === d.id}
                            className="btn-primary text-xs flex items-center space-x-2 py-2 px-4 shadow-lg shadow-indigo-500/20"
                          >
                            <Send className={`w-3.5 h-3.5 ${sendingId === d.id ? 'animate-bounce' : ''}`} />
                            <span>{sendingId === d.id ? 'Sending Email...' : 'Approve & Send'}</span>
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
  );
}
