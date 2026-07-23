import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import FilterBar from './components/FilterBar';
import JobCard from './components/JobCard';
import MethodAModal from './components/MethodAModal';
import MethodBModal from './components/MethodBModal';
import JobAssistantWorkflow from './components/JobAssistantWorkflow';
import TemplatesManager from './components/TemplatesManager';
import DraftQueue from './components/DraftQueue';
import SentLogsTracker from './components/SentLogsTracker';
import SettingsManager from './components/SettingsManager';
import AuthModal from './components/AuthModal';
import { api, getAuthToken, removeAuthToken } from './api';
import { Briefcase, AlertCircle } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('jobs');
  const [user, setUser] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);

  // Job Feed state & filters
  const [jobs, setJobs] = useState([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [fetchingAdzuna, setFetchingAdzuna] = useState(false);
  const [selectedRoles, setSelectedRoles] = useState(['data_analyst', 'data_scientist']);
  const [selectedCities, setSelectedCities] = useState([]);
  const [selectedExpBuckets, setSelectedExpBuckets] = useState(['0-1', '1-3']);
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [methodAJob, setMethodAJob] = useState(null);
  const [methodBJob, setMethodBJob] = useState(null);

  // Toast Notification
  const [toast, setToast] = useState(null);

  useEffect(() => {
    checkUser();
    window.addEventListener('auth-expired', handleAuthExpired);
    return () => window.removeEventListener('auth-expired', handleAuthExpired);
  }, []);

  useEffect(() => {
    if (activeTab === 'jobs') {
      fetchJobsList();
    }
  }, [selectedRoles, selectedCities, selectedExpBuckets, searchQuery, activeTab]);

  const checkUser = async () => {
    if (!getAuthToken()) {
      setUser(null);
      return;
    }
    try {
      const me = await api.getMe();
      setUser(me);
    } catch (err) {
      setUser(null);
    }
  };


  const handleAuthExpired = () => {
    setUser(null);
    showToast('Session expired. Please sign in again.', 'error');
  };

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchJobsList = async () => {
    setLoadingJobs(true);
    try {
      const params = {
        roles: selectedRoles,
        cities: selectedCities,
        exp_buckets: selectedExpBuckets,
        q: searchQuery,
      };
      const data = await api.getJobs(params);
      setJobs(data);
    } catch (err) {
      console.error('Error fetching jobs', err);
    } finally {
      setLoadingJobs(false);
    }
  };

  const handlePollAdzuna = async () => {
    setFetchingAdzuna(true);
    try {
      const res = await api.triggerFetchJobs();
      showToast(`Adzuna Fetch Complete: ${res.new_jobs} new jobs added.`, 'success');
      fetchJobsList();
    } catch (err) {
      showToast(err.message || 'Error fetching from Adzuna', 'error');
    } finally {
      setFetchingAdzuna(false);
    }
  };

  const handleLogout = () => {
    removeAuthToken();
    setUser(null);
    showToast('Logged out successfully.', 'success');
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={user}
        onLogout={handleLogout}
        onOpenAuth={() => setAuthOpen(true)}
      />

      {/* Toast Alert */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 animate-bounce">
          <div
            className={`px-5 py-3 rounded-xl shadow-2xl text-xs font-semibold flex items-center space-x-2 border ${
              toast.type === 'success'
                ? 'bg-emerald-950/90 border-emerald-500/40 text-emerald-200'
                : 'bg-red-950/90 border-red-500/40 text-red-200'
            }`}
          >
            <AlertCircle className="w-4 h-4" />
            <span>{toast.message}</span>
          </div>
        </div>
      )}

      {/* Main Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'jobs' && (
          <div>
            <FilterBar
              selectedRoles={selectedRoles}
              setSelectedRoles={setSelectedRoles}
              selectedCities={selectedCities}
              setSelectedCities={setSelectedCities}
              selectedExpBuckets={selectedExpBuckets}
              setSelectedExpBuckets={setSelectedExpBuckets}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              onFetchAdzuna={handlePollAdzuna}
              fetchingJobs={fetchingAdzuna}
            />

            {/* Jobs List */}
            {loadingJobs ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="glass-card p-6 h-64 animate-pulse bg-slate-900/40" />
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div className="glass-panel p-16 text-center">
                <Briefcase className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <h3 className="text-lg font-bold text-slate-300">No Job Listings Match Selected Filters</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                  Try clearing city or role filters, or click 'Poll Fresh Jobs (Adzuna API)' to fetch live postings from Adzuna.
                </p>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-4 px-1">
                  <span className="text-xs font-semibold text-slate-400">
                    Showing <strong className="text-slate-200">{jobs.length}</strong> matching postings (Sorted by newest first)
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {jobs.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      onApplyMethodA={(j) => setMethodAJob(j)}
                      onApplyMethodB={(j) => {
                        if (!user) {
                          setAuthOpen(true);
                          return;
                        }
                        setMethodBJob(j);
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'assistant' && <JobAssistantWorkflow />}
        {activeTab === 'templates' && <TemplatesManager />}
        {activeTab === 'drafts' && <DraftQueue />}
        {activeTab === 'logs' && <SentLogsTracker />}
        {activeTab === 'settings' && <SettingsManager />}

      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-slate-900 bg-slate-950 text-center text-xs text-slate-500">
        <p>Fresher Job Application Platform • Powered strictly by Official Adzuna REST API • Human-in-the-loop Email Architecture</p>
      </footer>

      {/* Modals */}
      {methodAJob && <MethodAModal job={methodAJob} onClose={() => setMethodAJob(null)} />}
      {methodBJob && (
        <MethodBModal
          job={methodBJob}
          user={user}
          onClose={() => setMethodBJob(null)}
          onCreatedDraft={() => showToast('Draft saved to queue!', 'success')}
        />
      )}
      {authOpen && (
        <AuthModal
          onClose={() => setAuthOpen(false)}
          onSuccess={(u) => {
            setUser(u);
            showToast(`Welcome back, ${u.full_name}!`, 'success');
          }}
        />
      )}
    </div>
  );
}
