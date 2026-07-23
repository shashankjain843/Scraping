import React from 'react';
import { Search, MapPin, Briefcase, Award, RefreshCw, Filter } from 'lucide-react';

const CITIES_LIST = [
  'Jaipur', 'Noida', 'Gurgaon', 'Delhi', 'Pune', 'Hyderabad', 'Bangalore', 'Ahmedabad'
];

export default function FilterBar({
  selectedRoles,
  setSelectedRoles,
  selectedCities,
  setSelectedCities,
  selectedExpBuckets,
  setSelectedExpBuckets,
  searchQuery,
  setSearchQuery,
  onFetchAdzuna,
  fetchingJobs
}) {
  const toggleRole = (role) => {
    if (selectedRoles.includes(role)) {
      setSelectedRoles(selectedRoles.filter((r) => r !== role));
    } else {
      setSelectedRoles([...selectedRoles, role]);
    }
  };

  const toggleCity = (city) => {
    if (selectedCities.includes(city)) {
      setSelectedCities(selectedCities.filter((c) => c !== city));
    } else {
      setSelectedCities([...selectedCities, city]);
    }
  };

  const toggleExpBucket = (bucket) => {
    if (selectedExpBuckets.includes(bucket)) {
      setSelectedExpBuckets(selectedExpBuckets.filter((b) => b !== bucket));
    } else {
      setSelectedExpBuckets([...selectedExpBuckets, bucket]);
    }
  };

  return (
    <div className="glass-panel p-5 mb-8">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        {/* Search Bar */}
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-3.5 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by job title, company name, or keywords (SQL, Python)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-700/60 rounded-xl text-sm text-slate-200 placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>

        {/* Fetch Adzuna Jobs Button */}
        <button
          onClick={onFetchAdzuna}
          disabled={fetchingJobs}
          className="btn-primary text-sm flex items-center justify-center space-x-2 shrink-0 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${fetchingJobs ? 'animate-spin' : ''}`} />
          <span>{fetchingJobs ? 'Fetching from Adzuna...' : 'Poll Fresh Jobs (Adzuna API)'}</span>
        </button>
      </div>

      {/* Filter Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        {/* Role Selector */}
        <div>
          <label className="flex items-center space-x-2 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            <Briefcase className="w-3.5 h-3.5 text-indigo-400" />
            <span>Target Role Category</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => toggleRole('data_analyst')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedRoles.includes('data_analyst')
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/50'
              }`}
            >
              Data Analyst
            </button>
            <button
              onClick={() => toggleRole('data_scientist')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedRoles.includes('data_scientist')
                  ? 'bg-cyan-600 text-white shadow-md shadow-cyan-500/20'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/50'
              }`}
            >
              Data Scientist
            </button>
          </div>
        </div>

        {/* Experience Bucket Selector */}
        <div>
          <label className="flex items-center space-x-2 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            <Award className="w-3.5 h-3.5 text-emerald-400" />
            <span>Experience Level</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => toggleExpBucket('0-1')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedExpBuckets.includes('0-1')
                  ? 'bg-emerald-600 text-white shadow-md shadow-emerald-500/20'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/50'
              }`}
            >
              Bucket A (0-1 Years)
            </button>
            <button
              onClick={() => toggleExpBucket('1-3')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                selectedExpBuckets.includes('1-3')
                  ? 'bg-amber-600 text-white shadow-md shadow-amber-500/20'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 border border-slate-700/50'
              }`}
            >
              Bucket B (1-3 Years / includes 1-2)
            </button>
          </div>
        </div>

        {/* Target Cities Filter */}
        <div>
          <label className="flex items-center space-x-2 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            <MapPin className="w-3.5 h-3.5 text-cyan-400" />
            <span>Target Indian Cities</span>
          </label>
          <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
            {CITIES_LIST.map((city) => {
              const isSelected = selectedCities.includes(city);
              return (
                <button
                  key={city}
                  onClick={() => toggleCity(city)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                    isSelected
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                      : 'bg-slate-800/40 text-slate-400 hover:text-slate-300 border border-slate-700/40'
                  }`}
                >
                  {city}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
