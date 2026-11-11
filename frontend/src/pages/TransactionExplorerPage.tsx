import React, { useMemo, useState } from 'react';
import { AgGridReact } from 'ag-grid-react';
import {
  ClientSideRowModelModule,
  ModuleRegistry,
  NumberFilterModule,
  PaginationModule,
  RowSelectionModule,
  TextFilterModule,
  themeQuartz,
} from 'ag-grid-community';
import type { ColDef, RowClickedEvent } from 'ag-grid-community';

import {
  Eye,
  Filter,
  Search,
} from 'lucide-react';
import { RiskBadge, StatusBadge } from '../components/common/StatusBadge';
import type { Transaction } from '../types';

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  PaginationModule,
  TextFilterModule,
  NumberFilterModule,
  RowSelectionModule,
]);

interface TransactionExplorerPageProps {
  transactions: Transaction[];
  onSelectTransaction: (id: string) => void;
  isLoading: boolean;
}

export const TransactionExplorerPage: React.FC<TransactionExplorerPageProps> = ({
  transactions,
  onSelectTransaction,
  isLoading,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDecision, setSelectedDecision] = useState('ALL');
  const [selectedStatus, setSelectedStatus] = useState('ALL');

  // Filtered rows based on search and dropdowns
  const filteredData = useMemo(() => {
    return transactions.filter((t) => {
      const matchesSearch =
        searchTerm === '' ||
        t.external_reference.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.merchant_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.merchant_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (t.paypal_order_id && t.paypal_order_id.toLowerCase().includes(searchTerm.toLowerCase()));

      const matchesDecision =
        selectedDecision === 'ALL' || t.decision === selectedDecision;

      const matchesStatus =
        selectedStatus === 'ALL' || t.payment_status === selectedStatus;

      return matchesSearch && matchesDecision && matchesStatus;
    });
  }, [transactions, searchTerm, selectedDecision, selectedStatus]);

  // Column definitions for AG Grid
  const columnDefs = useMemo<ColDef<Transaction>[]>(() => {
    return [
      {
        headerName: 'Reference',
        field: 'external_reference',
        minWidth: 150,
        cellRenderer: (params: any) => (
          <span className="font-mono font-semibold text-blue-600 hover:underline cursor-pointer">
            {params.value}
          </span>
        ),
      },
      {
        headerName: 'Merchant',
        field: 'merchant_name',
        minWidth: 180,
        cellRenderer: (params: any) => (
          <div>
            <div className="font-medium text-slate-900 leading-tight">{params.value}</div>
            <div className="text-[10px] text-slate-400 font-mono">{params.data?.merchant_id}</div>
          </div>
        ),
      },
      {
        headerName: 'Amount',
        field: 'amount',
        minWidth: 120,
        cellRenderer: (params: any) => (
          <span className="font-mono font-semibold text-slate-900">
            ${params.value} <span className="text-slate-400 text-[10px]">{params.data?.currency}</span>
          </span>
        ),
      },
      {
        headerName: 'Firewall Decision',
        field: 'decision',
        minWidth: 140,
        cellRenderer: (params: any) => <StatusBadge decision={params.value} />,
      },
      {
        headerName: 'Escrow Status',
        field: 'payment_status',
        minWidth: 160,
        cellRenderer: (params: any) => <StatusBadge status={params.value} />,
      },
      {
        headerName: 'Risk Score',
        field: 'risk_score',
        minWidth: 120,
        cellRenderer: (params: any) => <RiskBadge score={params.value} />,
      },
      {
        headerName: 'PayPal Order ID',
        field: 'paypal_order_id',
        minWidth: 160,
        cellRenderer: (params: any) =>
          params.value ? (
            <span className="font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded text-[11px]">
              {params.value}
            </span>
          ) : (
            <span className="text-slate-400 italic text-[11px]">Not created (Blocked)</span>
          ),
      },
      {
        headerName: 'Timestamp',
        field: 'created_at',
        minWidth: 150,
        cellRenderer: (params: any) => (
          <span className="text-slate-500 font-mono text-xs">
            {new Date(params.value).toLocaleString([], {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        ),
      },
      {
        headerName: 'Action',
        width: 100,
        sortable: false,
        filter: false,
        cellRenderer: (params: any) => (
          <button
            onClick={() => onSelectTransaction(params.data.id)}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors"
          >
            <Eye className="w-3.5 h-3.5" />
            <span>View</span>
          </button>
        ),
      },
    ];
  }, [onSelectTransaction]);

  const onRowClicked = (event: RowClickedEvent<Transaction>) => {
    if (event.data?.id) {
      onSelectTransaction(event.data.id);
    }
  };

  return (
    <div className="space-y-4">
      {/* Control Bar: Filters & Search */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search */}
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by reference, merchant, description, PayPal ID..."
            className="w-full pl-9 pr-4 py-2 text-xs border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 bg-slate-50/50"
          />
        </div>

        {/* Dropdowns */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>

          {/* Decision filter */}
          <select
            value={selectedDecision}
            onChange={(e) => setSelectedDecision(e.target.value)}
            className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 font-medium focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Decisions</option>
            <option value="APPROVE">APPROVE Only</option>
            <option value="REVIEW">REVIEW Only</option>
            <option value="BLOCK">BLOCK Only</option>
          </select>

          {/* Status filter */}
          <select
            aria-label="Filter by Escrow State"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 font-medium focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Escrow States</option>
            <option value="CAPTURED">CAPTURED</option>
            <option value="AUTHORIZED">AUTHORIZED</option>
            <option value="REVIEW_REQUIRED">REVIEW REQUIRED</option>
            <option value="HELD">HELD</option>
            <option value="BLOCKED">BLOCKED</option>
            <option value="VOIDED">VOIDED</option>
          </select>

          <div className="text-xs text-slate-400 font-mono">
            Showing <strong className="text-slate-700">{filteredData.length}</strong> of{' '}
            {transactions.length}
          </div>
        </div>
      </div>

      {/* AG Grid Container */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="w-full h-[620px]">
          <AgGridReact
            theme={themeQuartz}
            rowData={filteredData}
            columnDefs={columnDefs}
            defaultColDef={{
              sortable: true,
              filter: true,
              resizable: true,
            }}
            pagination={true}
            paginationPageSize={15}
            paginationPageSizeSelector={[10, 15, 25, 50]}
            onRowClicked={onRowClicked}
            loading={isLoading}
            rowSelection={{ mode: 'singleRow', checkboxes: false, enableClickSelection: true }}
          />
        </div>
      </div>
    </div>
  );
};
