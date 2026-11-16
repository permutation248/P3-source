import { type ReactNode } from 'react';

// ── StatusBadge ──

type BadgeVariant =
  | 'solved' | 'failed' | 'pending' | 'running' | 'timeout'
  | 'completed' | 'code' | 'proof' | 'auto';

const badgeStyles: Record<BadgeVariant, string> = {
  solved: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
  completed: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
  failed: 'bg-red-500/10 text-red-400 ring-red-500/20',
  pending: 'bg-ink-500/10 text-ink-400 ring-ink-500/20',
  running: 'bg-blue-500/10 text-blue-400 ring-blue-500/20',
  timeout: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
  code: 'bg-violet-500/10 text-violet-400 ring-violet-500/20',
  proof: 'bg-cyan-500/10 text-cyan-400 ring-cyan-500/20',
  auto: 'bg-accent-500/10 text-accent-400 ring-accent-500/20',
};

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase() as BadgeVariant;
  const style = badgeStyles[key] ?? 'bg-ink-100 text-ink-500 ring-ink-200';
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium font-mono ring-1 ring-inset ${style}`}
    >
      {status}
    </span>
  );
}

// ── LoadingSpinner ──

export function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = { sm: 'h-5 w-5', md: 'h-8 w-8', lg: 'h-12 w-12' };
  return (
    <div className="flex items-center justify-center py-16">
      <div className="flex flex-col items-center gap-3">
        <svg
          className={`animate-spin text-accent-500 ${sizeClasses[size]}`}
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path
            className="opacity-80"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z"
          />
        </svg>
        <span className="text-xs font-mono text-ink-400 tracking-wider">COMPUTING...</span>
      </div>
    </div>
  );
}

// ── MetricCard ──

interface MetricCardProps {
  label: string;
  value: string | number;
  trend?: { direction: 'up' | 'down'; text: string };
  icon?: ReactNode;
  accent?: 'default' | 'green' | 'blue' | 'violet' | 'amber';
}

const accentBorder: Record<string, string> = {
  default: 'border-l-ink-200',
  green: 'border-l-proof-green',
  blue: 'border-l-proof-blue',
  violet: 'border-l-proof-violet',
  amber: 'border-l-proof-amber',
};

export function MetricCard({ label, value, trend, icon, accent = 'default' }: MetricCardProps) {
  return (
    <div
      className={`rounded-lg border border-ink-100 border-l-[3px] ${accentBorder[accent]} bg-white p-4 shadow-card transition-shadow hover:shadow-card-hover`}
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-ink-400">{label}</p>
        {icon && <span className="text-ink-300">{icon}</span>}
      </div>
      <p className="mt-1.5 text-2xl font-semibold font-mono text-ink-800 tracking-tight">{value}</p>
      {trend && (
        <p
          className={`mt-1 text-xs font-medium ${
            trend.direction === 'up' ? 'text-proof-green' : 'text-proof-red'
          }`}
        >
          {trend.direction === 'up' ? '\u2191' : '\u2193'} {trend.text}
        </p>
      )}
    </div>
  );
}

// ── PageHeader ──

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  symbol?: string; // math symbol decoration
  actions?: ReactNode;
}

export function PageHeader({ title, subtitle, symbol = '⊢', actions }: PageHeaderProps) {
  return (
    <div className="mb-8 flex items-start justify-between">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-ink-900">
          <span className="font-mono text-accent-400 opacity-60">{symbol}</span>
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 text-sm text-ink-400">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

// ── SectionCard ──

interface SectionCardProps {
  title?: string;
  children: ReactNode;
  className?: string;
}

export function SectionCard({ title, children, className = '' }: SectionCardProps) {
  return (
    <div className={`rounded-xl border border-ink-100 bg-white shadow-card ${className}`}>
      {title && (
        <div className="border-b border-ink-100 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-ink-700 tracking-wide uppercase">
            {title}
          </h2>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── DataTable ──

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render?: (row: T) => ReactNode;
  mono?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (key: string) => void;
  onRowClick?: (row: T) => void;
  rowKey: (row: T) => string | number;
}

export function DataTable<T>({
  columns,
  data,
  sortBy,
  sortOrder,
  onSort,
  onRowClick,
  rowKey,
}: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto rounded-xl border border-ink-100 bg-white shadow-card">
      <table className="min-w-full divide-y divide-ink-100">
        <thead>
          <tr className="bg-ink-50/60">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-400 ${
                  col.sortable ? 'cursor-pointer select-none hover:text-ink-600' : ''
                }`}
                onClick={() => col.sortable && onSort?.(col.key)}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && sortBy === col.key && (
                    <span className="text-accent-500">{sortOrder === 'asc' ? '\u25B2' : '\u25BC'}</span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-50">
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-ink-300">
                <span className="font-mono">-- empty --</span>
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={rowKey(row)}
                className={`transition-colors ${
                  onRowClick
                    ? 'cursor-pointer hover:bg-accent-50/40'
                    : ''
                }`}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`whitespace-nowrap px-4 py-3 text-sm text-ink-700 ${
                      col.mono ? 'font-mono text-xs' : ''
                    }`}
                  >
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Form components ──

interface FormFieldProps {
  label: string;
  hint?: string;
  children: ReactNode;
}

export function FormField({ label, hint, children }: FormFieldProps) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-ink-600">
        {label}
        {hint && <span className="ml-1.5 font-normal text-ink-300">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

export const inputClass =
  'w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 shadow-sm placeholder:text-ink-300 transition-colors focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-400/20';

export const selectClass =
  'w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 shadow-sm transition-colors focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-400/20';

export const btnPrimary =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-accent-500 disabled:opacity-50';

export const btnSecondary =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-ink-200 bg-white px-4 py-2.5 text-sm font-medium text-ink-600 shadow-sm transition-colors hover:bg-ink-50 disabled:opacity-50';
