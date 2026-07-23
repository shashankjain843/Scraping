import React, { useState } from 'react';
import { ExternalLink, Mail, MapPin, Building, Calendar, ChevronDown, ChevronUp, Sparkles, DollarSign } from 'lucide-react';

export default function JobCard({ job, onApplyMethodA, onApplyMethodB }) {
  const [expanded, setExpanded] = useState(false);

  const formatDate = (isoString) => {
    if (!isoString) return 'Recently';
    const dt = new Date(isoString);
    return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  const formatSalary = (min, max) => {
    if (!min && !max) return null;
    const formatLakhs = (val) => (val / 100000).toFixed(1) + ' LPA';
    if (min && max) return `${formatLakhs(min)} - ${formatLakhs(max)}`;
    if (min) return `From ${formatLakhs(min)}`;
    if (max) return `Up to ${formatLakhs(max)}`;
    return null;
  };

  const salaryText = formatSalary(job.salary_min, job.salary_max);

  return (
    <div className="glass-card p-6 flex flex-col justify-between h-full">
      <div>
        {/* Header Badges */}
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex flex-wrap items-center gap-2">
            {job.role_category === 'data_analyst' ? (
              <span className="badge-indigo">Data Analyst</span>
            ) : (
              <span className="badge-cyan">Data Scientist</span>
            )}

            <span className="badge-amber flex items-center space-x-1">
              <MapPin className="w-3 h-3" />
              <span>{job.city}</span>
            </span>

            {job.bucket_0_1 && <span className="badge-emerald">0-1 Yrs (Bucket A)</span>}
            {job.bucket_1_3 && <span className="badge-indigo">1-3 Yrs (Bucket B)</span>}
          </div>

          <div className="flex items-center text-xs text-slate-400 space-x-1">
            <Calendar className="w-3.5 h-3.5" />
            <span>{formatDate(job.created_at)}</span>
          </div>
        </div>

        {/* Title & Company */}
        <h3 className="text-lg font-bold text-slate-100 mb-1 line-clamp-2 hover:text-indigo-300 transition">
          {job.title}
        </h3>
        
        <div className="flex items-center space-x-2 text-sm text-slate-400 mb-3">
          <Building className="w-4 h-4 text-slate-500" />
          <span className="font-medium text-slate-300">{job.company}</span>
          <span>•</span>
          <span className="text-xs text-slate-400">{job.location}</span>
        </div>

        {salaryText && (
          <div className="flex items-center space-x-1 text-xs font-semibold text-emerald-400 mb-3">
            <DollarSign className="w-3.5 h-3.5" />
            <span>{salaryText}</span>
          </div>
        )}

        {/* Description Snippet */}
        <div className="text-sm text-slate-300/80 mb-4 leading-relaxed">
          <p className={expanded ? '' : 'line-clamp-3'}>{job.description}</p>
          {job.description && job.description.length > 180 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-1 text-xs font-medium text-indigo-400 hover:text-indigo-300 flex items-center space-x-1"
            >
              <span>{expanded ? 'Show Less' : 'Read Full Description'}</span>
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          )}
        </div>
      </div>

      {/* Action Buttons: Method A and Method B */}
      <div className="pt-4 border-t border-slate-800 flex flex-col sm:flex-row items-center gap-2">
        <button
          onClick={() => onApplyMethodA(job)}
          className="w-full sm:flex-1 btn-primary text-xs flex items-center justify-center space-x-2 py-2.5"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          <span>Apply via Official Link</span>
        </button>

        <button
          onClick={() => onApplyMethodB(job)}
          className="w-full sm:flex-1 btn-secondary text-xs flex items-center justify-center space-x-2 py-2.5"
        >
          <Mail className="w-3.5 h-3.5 text-indigo-400" />
          <span>Apply via Email (Draft)</span>
        </button>
      </div>
    </div>
  );
}
