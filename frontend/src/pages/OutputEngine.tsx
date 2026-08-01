import { useQuery } from '@tanstack/react-query'

import { apiClient, toApiError } from '@/api/client'
import PageHeader from '@/components/PageHeader'
import DataState from '@/components/DataState'
import EntityTable from '@/components/EntityTable'

export default function OutputEngine() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['output-templates'],
    queryFn: async () => {
      const res = await apiClient.get<Record<string, unknown>[]>('/outputs/')
      return res.data
    },
  })

  return (
    <div>
      <PageHeader title="Output Engine" description="Output templates" />

      <DataState
        isLoading={isLoading}
        error={error ? toApiError(error) : null}
        data={data}
        isEmpty={(rows) => rows.length === 0}
        emptyMessage="No output templates yet."
      >
        {(rows) => (
          <EntityTable rows={rows} columns={['name', 'output_type', 'output_format']} />
        )}
      </DataState>
    </div>
  )
}
