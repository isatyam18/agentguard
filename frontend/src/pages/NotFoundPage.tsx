import React from 'react';
import { ArrowLeft, Compass, ShieldAlert } from 'lucide-react';
import { ROUTES } from '../routes';

interface NotFoundPageProps {
  requestedPath: string;
  onNavigate: (path: string, event?: React.MouseEvent<HTMLAnchorElement>) => void;
}

export const NotFoundPage: React.FC<NotFoundPageProps> = ({ requestedPath, onNavigate }) => {
  const destinations = Object.values(ROUTES);

  return (
    <div className="max-w-2xl mx-auto py-12">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-8 text-center space-y-6">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-navy-900 flex items-center justify-center shadow-md border border-slate-200">
            <img
              src="/favicon.svg"
              alt="AgentGuard policy firewall shield logo"
              width={44}
              height={44}
              className="w-11 h-11"
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-xs font-semibold font-mono">
            <ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />
            <span>HTTP 404 — Route Blocked or Not Found</span>
          </div>

          <h2 className="text-xl font-bold text-slate-900 pt-1">
            No AgentGuard view exists at <code className="font-mono text-rose-600">{requestedPath}</code>
          </h2>

          <p className="text-sm text-slate-600 max-w-md mx-auto">
            The route you requested is not registered in the AgentGuard Security Console. Return to the main dashboard or select one of the verified destinations below.
          </p>
        </div>

        <div className="pt-2">
          <a
            href="/"
            onClick={(e) => onNavigate('/', e)}
            className="inline-flex items-center gap-2 px-5 py-2.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs transition-colors"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            <span>Return to Overview</span>
          </a>
        </div>

        <div className="pt-6 border-t border-slate-100 text-left">
          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">
            <Compass className="w-3.5 h-3.5 text-blue-600" aria-hidden="true" />
            <span>Verified Console Routes</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {destinations.map((dest) => (
              <a
                key={dest.id}
                href={dest.path}
                onClick={(e) => onNavigate(dest.path, e)}
                className="p-3 rounded-lg border border-slate-200 hover:border-blue-400 hover:bg-blue-50/40 transition-colors flex flex-col"
              >
                <span className="text-xs font-semibold text-slate-900">{dest.label}</span>
                <span className="text-[11px] font-mono text-slate-500">{dest.path}</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
