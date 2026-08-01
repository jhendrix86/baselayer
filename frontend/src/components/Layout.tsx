import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Workflow,
  DollarSign,
  BookOpen,
  FileText,
  Bot,
  Shield,
  FileOutput,
  Settings as SettingsIcon,
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/core-loop', label: 'Core Loop', icon: Workflow },
  { to: '/income-engine', label: 'Income Engine', icon: DollarSign },
  { to: '/codex', label: 'Codex', icon: BookOpen },
  { to: '/protocols', label: 'Protocols', icon: FileText },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/governance', label: 'Governance', icon: Shield },
  { to: '/output-engine', label: 'Output Engine', icon: FileOutput },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 flex-none flex-col border-r border-gray-200 bg-white">
        <div className="flex h-16 items-center border-b border-gray-200 px-6">
          <span className="font-mono text-lg font-semibold text-gray-900">BaseLayer</span>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                )
              }
            >
              <Icon className="h-4 w-4 flex-none" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-200 px-6 py-4 text-xs text-gray-400">
          governance-grade operational system
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 flex-none items-center border-b border-gray-200 bg-white px-6">
          <span className="text-sm text-gray-500">Autonomous Company OS</span>
        </header>
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </div>
  )
}
