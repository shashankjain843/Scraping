import React, { useState, useEffect } from 'react';
import { History, CheckCircle, AlertTriangle, Search, Eye, X, Building, Mail } from 'lucide-react';
import { api } from '../api';

export default function SentLogsTracker() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('');
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await api.getSentLogs();
      setLogs(data);
    } catch (err) {
      console.error('Error fetching sent logs', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter((l) => {
    if (!filter) return true;
    const f = filter.toLowerCase();
    return (
      (l.job_title && l.job_title.toLowerCase().includes(f)) ||
      (l.company_name && l.company_name.toLowerCase().includes(f)) ||
      (l.recipient_email && l.recipient_email.toLowerCase().includes(f))
    );
  });

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    const dt = new Date(isoString);
    return dt.toLocaleString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Personal Sent History Tracker</h2>
          <p className="text-xs text-slate-400">Personal sent log of all outgoing job application emails and delivery statuses.</p>
        </div>

        <div className="relative w-full md:w-72">
          <Search className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search sent log..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200"
          />
        </div>
      </div>

      {logs.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <History className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-300">No Sent Emails Recorded</h3>
          <p className="text-xs text-slate-500 mt-1">Sent emails triggered by your explicit action will be logged here for tracking.</p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/60 uppercase tracking-wider text-[11px] text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Job Title & Company</th>
                  <th className="py-3.5 px-4 font-semibold">Recipient Email</th>
                  <th className="py-3.5 px-4 font-semibold">Sent Timestamp</th>
                  <th className="py-3.5 px-4 font-semibold">Status</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-900/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-200">{log.job_title || 'Application'}</div>
                      <div className="text-[11px] text-slate-400 flex items-center space-x-1 mt-0.5">
                        <Building className="w-3 h-3 text-slate-500" />
                        <span>{log.company_name}</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono text-cyan-300">
                      {log.recipient_email}
                    </td>

                    <td className="py-3.5 px-4 text-slate-400">
                      {formatDate(log.sent_at)}
                    </td>

                    <td className="py-3.5 px-4">
                      {log.status === 'sent' ? (
                        <span className="badge-emerald inline-flex items-center space-x-1">
                          <CheckCircle className="w-3 h-3" />
                          <span>Sent</span>
                        </span>
                      ) : (
                        <span className="badge-amber text-red-400 bg-red-950/40 border-red-500/30 inline-flex items-center space-x-1">
                          <AlertTriangle className="w-3 h-3" />
                          <span>Failed</span>
                        </span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="p-1.5 text-slate-400 hover:text-slate-200 bg-slate-800/60 hover:bg-slate-800 rounded-lg transition"
                        title="View Email Copy"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Log Details Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
          <div className="glass-panel w-full max-w-2xl p-6 relative">
            <button
              onClick={() => setSelectedLog(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-lg font-bold text-slate-100 mb-2">{selectedLog.job_title}</h3>
            <p className="text-xs text-slate-400 mb-4 font-mono">
              Sent To: <span className="text-cyan-300 font-semibold">{selectedLog.recipient_email}</span> | Date: {formatDate(selectedLog.sent_at)}
            </p>

            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Subject</label>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-xl text-xs font-semibold text-slate-200">
                {selectedLog.subject}
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Sent Content</label>
              <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                {selectedLog.body}
              </div>
            </div>

            <div className="flex justify-end">
              <button onClick={() => setSelectedLog(null)} className="btn-secondary text-xs">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
