function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function toColumnLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

interface EntityTableProps {
  rows: Record<string, unknown>[]
  /** Optional explicit column order/subset; defaults to every key on the first row. */
  columns?: string[]
}

/**
 * Renders whatever shape the API actually returns as a table, deriving
 * columns from the real response instead of hardcoding a schema that might
 * drift from the backend.
 */
export default function EntityTable({ rows, columns }: EntityTableProps) {
  const cols = columns ?? Object.keys(rows[0] ?? {})

  return (
    <div className="card overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {cols.map((col) => (
              <th
                key={col}
                className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
              >
                {toColumnLabel(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.map((row, i) => (
            <tr key={(row.id as string) ?? i} className="hover:bg-gray-50">
              {cols.map((col) => (
                <td key={col} className="max-w-xs truncate px-4 py-3 text-sm text-gray-700">
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
