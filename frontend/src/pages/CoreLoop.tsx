import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import EntityTable from '@/components/EntityTable'

const STATUSES = ['draft', 'active', 'paused', 'completed', 'failed', 'cancelled'] as const

export default function CoreLoop() {
  const [status, setStatus] = useState<string>('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['workflows', status],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>[]>('/workflows/', {
        params: status ? { status } : undefined,
      })
      return res.data
    },
  })

  return (
    <div>
      <PageHeader title="Core Loop" description="Workflow orchestration and execution" />

      <div className="mb-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="input w-48"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <DataState
        isLoading={isLoading}
        error={error ? toApiError(error) : null}
        data={data}
        isEmpty={(rows) => rows.length === 0}
        emptyMessage="No workflows found."
      >
        {(rows) => (
          <EntityTable
            rows={rows}
            columns={['name', 'status', 'category', 'priority', 'created_at']}
          />
        )}
      </DataState>
    </div>
  )
}
