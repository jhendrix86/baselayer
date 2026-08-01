import { useQuery } from '@tanstack/react-query'
import { subDays } from 'date-fns'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import EntityTable from '@/components/EntityTable'

const periodEnd = new Date()
const periodStart = subDays(periodEnd, 30)

export default function IncomeEngine() {
  const overview = useQuery({
    queryKey: ['revenue-overview'],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>>('/revenue/overview', {
        params: { period_start: periodStart.toISOString(), period_end: periodEnd.toISOString() },
      })
      return res.data
    },
  })

  const streams = useQuery({
    queryKey: ['revenue-streams'],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>[]>('/revenue/streams')
      return res.data
    },
  })

  return (
    <div>
      <PageHeader title="Income Engine" description="Revenue streams and billing, last 30 days" />

      <div className="mb-6">
        <DataState isLoading={overview.isLoading} error={overview.error ? toApiError(overview.error) : null} data={overview.data}>
          {(data) => (
            <div className="card p-5">
              <h2 className="mb-3 text-sm font-medium text-gray-500">Revenue overview</h2>
              <pre className="overflow-x-auto rounded bg-gray-50 p-3 text-xs text-gray-700">
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          )}
        </DataState>
      </div>

      <h2 className="mb-2 text-sm font-medium text-gray-500">Revenue streams</h2>
      <DataState
        isLoading={streams.isLoading}
        error={streams.error ? toApiError(streams.error) : null}
        data={streams.data}
        isEmpty={(rows) => rows.length === 0}
        emptyMessage="No revenue streams configured yet."
      >
        {(rows) => (
          <EntityTable rows={rows} columns={['name', 'revenue_type', 'pricing_model', 'status']} />
        )}
      </DataState>
    </div>
  )
}
