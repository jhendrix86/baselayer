import { AlertTriangle, Loader2, Inbox } from 'lucide-react'
import { ApiError } from '@/api/client'

interface DataStateProps<T> {
  isLoading: boolean
  error: ApiError | null
  data: T | undefined
  isEmpty?: (data: T) => boolean
  emptyMessage?: string
  children: (data: T) => React.ReactNode
}

/**
 * Renders one of loading / error / empty / content for a react-query result,
 * so every page doesn't have to reimplement the same three branches.
 */
export default function DataState<T>({
  isLoading,
  error,
  data,
  isEmpty,
  emptyMessage = 'Nothing here yet.',
  children,
}: DataStateProps<T>) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-400">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2 text-sm">Loading...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <AlertTriangle className="h-8 w-8 text-danger-500" />
        <p className="mt-2 text-sm font-medium text-gray-900">Couldn't load this data</p>
        <p className="mt-1 text-sm text-gray-500">
          {error.status ? `${error.status}: ` : ''}
          {error.message}
        </p>
      </div>
    )
  }

  if (data === undefined || (isEmpty && isEmpty(data))) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center text-gray-400">
        <Inbox className="h-8 w-8" />
        <p className="mt-2 text-sm">{emptyMessage}</p>
      </div>
    )
  }

  return <>{children(data)}</>
}
