import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useLocation } from 'react-router-dom'
import toast from 'react-hot-toast'
import { LogIn } from 'lucide-react'

import { apiClient, toApiError } from '@/api/client'
import { useAuthStore } from '@/store/authStore'

const loginSchema = z.object({
  email: z.string().email('Enter a valid email'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof loginSchema>

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: { id: string; email: string; name: string; role: string }
}

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const login = useAuthStore((s) => s.login)
  const [submitting, setSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })

  const onSubmit = async (values: LoginForm) => {
    setSubmitting(true)
    try {
      const { data } = await apiClient.post<LoginResponse>('/auth/login', values)
      login(
        { access_token: data.access_token, refresh_token: data.refresh_token },
        data.user
      )
      const from = (location.state as { from?: string } | undefined)?.from || '/dashboard'
      navigate(from, { replace: true })
    } catch (error) {
      toast.error(toApiError(error).message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-mono text-2xl font-semibold text-gray-900">BaseLayer</h1>
          <p className="mt-1 text-sm text-gray-500">Sign in to the operational console</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="card p-6">
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="input mt-1"
                {...register('email')}
              />
              {errors.email && <p className="mt-1 text-xs text-danger-600">{errors.email.message}</p>}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="input mt-1"
                {...register('password')}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-danger-600">{errors.password.message}</p>
              )}
            </div>

            <button type="submit" disabled={submitting} className="btn btn-primary w-full">
              <LogIn className="mr-2 h-4 w-4" />
              {submitting ? 'Signing in...' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
