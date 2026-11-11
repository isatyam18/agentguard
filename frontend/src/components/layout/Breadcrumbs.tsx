import React from 'react';
import { ChevronRight, Home } from 'lucide-react';
import type { RouteMetadata } from '../../routes';

interface BreadcrumbsProps {
  route: RouteMetadata;
  onNavigate: (path: string, event?: React.MouseEvent<HTMLAnchorElement>) => void;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ route, onNavigate }) => {
  return (
    <nav aria-label="Breadcrumb" className="mb-5 flex items-center text-xs text-slate-500">
      <ol className="flex items-center gap-1.5">
        <li>
          <a
            href="/"
            onClick={(e) => onNavigate('/', e)}
            className="inline-flex items-center gap-1.5 font-medium text-slate-600 hover:text-blue-600 transition-colors"
          >
            <Home className="w-3.5 h-3.5" aria-hidden="true" />
            <span>AgentGuard</span>
          </a>
        </li>

        <li aria-hidden="true" className="text-slate-400">
          <ChevronRight className="w-3.5 h-3.5" />
        </li>

        <li>
          {route.path === '/' ? (
            <span className="font-semibold text-slate-900" aria-current="page">
              Overview
            </span>
          ) : (
            <span className="font-semibold text-slate-900" aria-current="page">
              {route.label}
            </span>
          )}
        </li>
      </ol>
    </nav>
  );
};
