import { useQuery } from '@tanstack/react-query'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import EntityTable from '@/components/EntityTable'

export default function Governance() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['governance-policies'],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>[]>('/governance/')
      return res.data
    },
  })

  return (
    <div>
      <PageHeader title="Governance" description="Policy rules and compliance enforcement" />

      <DataState
        isLoading={isLoading}
        error={error ? toApiError(error) : null}
        data={data}
        isEmpty={(rows) => rows.length === 0}
        emptyMessage="No governance rules defined yet."
      >
        {(rows) => (
          <EntityTable rows={rows} columns={['name', 'category', 'priority', 'status']} />
        )}
      </DataState>
    </div>
  )
}
