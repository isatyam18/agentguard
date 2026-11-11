import React from 'react';
import type { Decision, PaymentStatus } from '../../types';

interface StatusBadgeProps {
  status?: PaymentStatus | string;
  decision?: Decision | string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, decision }) => {
  if (decision) {
    switch (decision) {
      case 'APPROVE':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            APPROVE
          </span>
        );
      case 'REVIEW':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            REVIEW
          </span>
        );
      case 'BLOCK':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            BLOCK
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-300">
            {decision}
          </span>
        );
    }
  }

  if (status) {
    switch (status) {
      case 'CAPTURED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            CAPTURED
          </span>
        );
      case 'AUTHORIZED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
            AUTHORIZED
          </span>
        );
      case 'REVIEW_REQUIRED':
      case 'HELD':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            {status === 'HELD' ? 'HELD (REVIEW)' : 'REVIEW REQUIRED'}
          </span>
        );
      case 'BLOCKED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
            BLOCKED
          </span>
        );
      case 'VOIDED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-300">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
            VOIDED
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-300">
            FAILED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  }

  return null;
};

export const RiskBadge: React.FC<{ score: number | string }> = ({ score }) => {
  const numScore = typeof score === 'string' ? Math.round(parseFloat(score) * (parseFloat(score) <= 1.0 ? 100 : 1)) : Math.round(score);

  let colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  let label = 'LOW';

  if (numScore >= 70) {
    colorClasses = 'bg-rose-50 text-rose-700 border-rose-200 font-bold';
    label = 'HIGH';
  } else if (numScore >= 35) {
    colorClasses = 'bg-amber-50 text-amber-700 border-amber-200 font-medium';
    label = 'MED';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs border ${colorClasses}`}>
      <span className="font-mono">{numScore}/100</span>
      <span className="text-[10px] uppercase tracking-wider opacity-75">({label})</span>
    </span>
  );
};
