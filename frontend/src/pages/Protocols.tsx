import { FileText } from 'lucide-react'
import PageHeader from '@/components/PageHeader'

/**
 * The backend's own /api/v1/status endpoint lists "protocols" as a
 * subsystem, but there is no protocols API router anywhere in baselayer
 * (confirmed 2026-08-01 - no backend/src/baselayer/protocols/api/ exists).
 * Rather than call a route that doesn't exist, this page says so honestly.
 */
export default function Protocols() {
  return (
    <div>
      <PageHeader title="Protocols" description="Protocol definitions and templates" />
      <div className="card flex flex-col items-center justify-center gap-2 py-16 text-center">
        <FileText className="h-8 w-8 text-gray-300" />
        <p className="text-sm font-medium text-gray-900">No API yet for this subsystem</p>
        <p className="max-w-sm text-sm text-gray-500">
          The backend's status endpoint lists "protocols" as a planned subsystem, but no
          protocols API router has been built yet -- there's nothing real to show here until
          that exists.
        </p>
      </div>
    </div>
  )
}
