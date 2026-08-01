interface StatCardProps {
  label: string
  value: string | number
  icon?: React.ReactNode
}

export default function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-gray-500">{label}</p>
        {icon}
      </div>
      <p className="mt-2 text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  )
}
