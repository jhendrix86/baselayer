import { useQuery } from '@tanstack/react-query'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import EntityTable from '@/components/EntityTable'

export default function Codex() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['knowledge-entries'],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>[]>('/knowledge/entries')
      return res.data
    },
  })

  return (
    <div>
      <PageHeader title="Codex" description="Knowledge base entries" />

      <DataState
        isLoading={isLoading}
        error={error ? toApiError(error) : null}
        data={data}
        isEmpty={(rows) => rows.length === 0}
        emptyMessage="No knowledge entries yet."
      >
        {(rows) => (
          <EntityTable rows={rows} columns={['title', 'knowledge_type', 'status', 'created_at']} />
        )}
      </DataState>
    </div>
  )
}
