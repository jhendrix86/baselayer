import { useQuery } from '@tanstack/react-query'
import { Workflow, Clock } from 'lucide-react'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import StatCard from '@/components/StatCard'

interface DashboardData {
  performance: Record<string, unknown>
  scheduled_workflows: {
    total: number
    active: number
    next_executions: Record<string, unknown>[]
  }
  active_executions: Record<string, unknown>
  timestamp: string
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const res = await apiClient.get<DashboardData>('/monitoring/dashboard')
      return res.data
    },
  })

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live workflow monitoring across the Core Loop engine"
      />

      <DataState isLoading={isLoading} error={error ? toApiError(error) : null} data={data}>
        {(dashboard) => (
          <div className="space-y-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <StatCard
                label="Scheduled workflows"
                value={dashboard.scheduled_workflows.total}
                icon={<Workflow className="h-5 w-5 text-primary-500" />}
              />
              <StatCard
                label="Active workflows"
                value={dashboard.scheduled_workflows.active}
                icon={<Clock className="h-5 w-5 text-governance-500" />}
              />
            </div>

            <div className="card p-5">
              <h2 className="mb-3 text-sm font-medium text-gray-500">Performance summary</h2>
              <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-xs text-gray-700">
                {JSON.stringify(dashboard.performance, null, 2)}
              </pre>
            </div>

            <p className="text-xs text-gray-400">
              Last updated: {new Date(dashboard.timestamp).toLocaleString()}
            </p>
          </div>
        )}
      </DataState>
    </div>
  )
}
