import { Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FlaskConical,
  GitCompareArrows,
  Upload,
  Plus,
  BookOpen,
  Settings,
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Experiments from './pages/Experiments';
import ExperimentDetail from './pages/ExperimentDetail';
import NewExperiment from './pages/NewExperiment';
import Compare from './pages/Compare';
import UploadPage from './pages/Upload';
import SettingsPage from './pages/Settings';
import { useApiKey } from './contexts/ApiKeyContext';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/experiments', label: 'Experiments', icon: FlaskConical },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows },
  { to: '/upload', label: 'Datasets', icon: Upload },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function SidebarLink({
  to,
  label,
  icon: Icon,
  end,
}: {
  to: string;
  label: string;
  icon: React.ComponentType<{ size?: number }>;
  end?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `nav-item ${isActive ? 'nav-item-active' : 'nav-item-inactive'}`
      }
    >
      <Icon size={18} />
      <span>{label}</span>
    </NavLink>
  );
}

export default function App() {
  const navigate = useNavigate();
  const { hasApiKey } = useApiKey();
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r border-slate-200 bg-[#f7f8fb] shadow-[2px_0_10px_rgba(15,23,42,0.04)]">
        <div className="flex items-center gap-3 px-5 py-6">
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-slate-900">
              Anonymous
            </h1>
            <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-slate-500">
              Prover
            </p>
          </div>
        </div>

        {/* Divider */}
        <div className="mx-4 border-t border-slate-200" />

        {/* Nav */}
        <nav className="flex-1 space-y-0.5 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <SidebarLink key={item.to} {...item} />
          ))}
        </nav>

        {/* New Experiment Button */}
        <div className="px-3 pb-4">
          <button
              onClick={() => navigate('/experiments/new')}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-600 px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-500"
            >
              <Plus size={16} />
              New Experiment
            </button>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 px-4 py-3 space-y-2">
          <div className="flex items-center gap-2 text-[10px] text-slate-500">
            <BookOpen size={12} />
            <span className="font-mono tracking-wider">Lean 4 / Mathlib</span>
          </div>
          <div className="flex items-center gap-2 text-[10px]">
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${hasApiKey ? 'bg-emerald-400' : 'bg-slate-300'}`} />
            <span className={`font-mono tracking-wider ${hasApiKey ? 'text-emerald-600' : 'text-slate-400'}`}>
              {hasApiKey ? 'API Key Set' : 'No API Key'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/experiments" element={<Experiments />} />
            <Route path="/experiments/new" element={<NewExperiment />} />
            <Route path="/experiments/:id" element={<ExperimentDetail />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
