import { useQuery } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { apiClient, toApiError } from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'

interface ApiStatus {
  status: string
  subsystems: Record<string, string>
  governance: Record<string, string>
}

export default function Settings() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const { data, isLoading, error } = useQuery({
    queryKey: ['api-status'],
    queryFn: async () => {
      const res = await apiClient.get<ApiStatus>('/status')
      return res.data
    },
  })

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="max-w-xl">
      <PageHeader title="Settings" />

      <div className="card mb-6 p-5">
        <h2 className="mb-3 text-sm font-medium text-gray-500">Signed in as</h2>
        {user ? (
          <div className="text-sm text-gray-900">
            <p className="font-medium">{user.name}</p>
            <p className="text-gray-500">{user.email}</p>
            <p className="mt-1 text-xs uppercase tracking-wide text-gray-400">{user.role}</p>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Not signed in.</p>
        )}
        <button onClick={handleLogout} className="btn btn-secondary mt-4">
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </button>
      </div>

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-medium text-gray-500">System status</h2>
        <DataState isLoading={isLoading} error={error ? toApiError(error) : null} data={data}>
          {(status) => (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">API</dt>
                <dd className="font-medium text-gray-900">{status.status}</dd>
              </div>
              {Object.entries(status.subsystems).map(([name, subsystemStatus]) => (
                <div key={name} className="flex justify-between">
                  <dt className="text-gray-500">{name}</dt>
                  <dd className="font-medium text-gray-900">{subsystemStatus}</dd>
                </div>
              ))}
            </dl>
          )}
        </DataState>
      </div>
    </div>
  )
}
