import { Outlet, Link, useLocation } from 'react-router-dom';
import { Home, Server, Zap, Moon, Sun } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useTeam } from '../contexts/TeamContext';

export default function Layout() {
  const [isDark, setIsDark] = useState(true); // Default to dark per guidelines
  const location = useLocation();
  const { selectedTeam, setSelectedTeam } = useTeam();

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const navItems = [
    { path: '/', label: 'Overview', icon: <Home className="w-5 h-5" /> },
    { path: '/utilization', label: 'Utilization', icon: <Server className="w-5 h-5" /> },
    { path: '/optimizations', label: 'Optimizations', icon: <Zap className="w-5 h-5" /> },
  ];

  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-[#09090b] text-zinc-950 dark:text-zinc-50 transition-colors">
      {/* Sidebar */}
      <div className="w-64 bg-white dark:bg-[#0c0c0f] border-r border-zinc-200 dark:border-zinc-800 flex flex-col">
        <div className="p-6">
          <h1 className="text-xl font-extrabold tracking-tight">Cloud FinOps</h1>
        </div>
        <nav className="flex-1 px-4 flex flex-col gap-2">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-colors ${
                location.pathname === item.path
                  ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400'
                  : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800/50'
              }`}
            >
              {item.icon}
              <span className="font-medium text-sm">{item.label}</span>
            </Link>
          ))}
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-16 flex items-center justify-between px-8 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0c0f]">
          <div className="flex items-center gap-6">
            <h2 className="text-lg font-semibold tracking-tight">
              {navItems.find((i) => i.path === location.pathname)?.label || 'Dashboard'}
            </h2>
            <div className="h-4 w-px bg-zinc-300 dark:bg-zinc-700 hidden sm:block"></div>
            <div className="hidden sm:flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <span className="font-medium">Team:</span>
              <select 
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
                className="bg-transparent border-none text-zinc-900 dark:text-zinc-100 font-medium focus:ring-0 cursor-pointer outline-none"
              >
                <option value="all">All Teams</option>
                <option value="data-platform">Data Platform</option>
                <option value="core-services">Core Services</option>
                <option value="marketing-ai">Marketing AI</option>
              </select>
            </div>
          </div>
          
          <button
            onClick={() => setIsDark(!isDark)}
            className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 transition-colors"
          >
            {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </header>

        {/* Scrollable Content */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-[1600px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

