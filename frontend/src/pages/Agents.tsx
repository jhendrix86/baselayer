import { useQuery } from '@tanstack/react-query'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import EntityTable from '@/components/EntityTable'

export default function Agents() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>[]>('/agents/')
      return res.data
    },
  })

  return (
    <div>
      <PageHeader title="Agents" description="Multi-agent orchestration" />

      <DataState
        isLoading={isLoading}
        error={error ? toApiError(error) : null}
        data={data}
        isEmpty={(rows) => rows.length === 0}
        emptyMessage="No agents registered yet."
      >
        {(rows) => <EntityTable rows={rows} columns={['name', 'agent_type', 'status', 'model']} />}
      </DataState>
    </div>
  )
}
