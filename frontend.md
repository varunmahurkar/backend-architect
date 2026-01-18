# Frontend Integration Guide

Simple, ChatGPT-style authentication using shadcn/ui components.

---

## 1. Install Dependencies

```bash
npm install @supabase/supabase-js @supabase/ssr
```

---

## 2. Environment Variables

Add to `.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 3. Supabase Client

### `lib/supabase/client.ts`

```typescript
import { createBrowserClient } from '@supabase/ssr'

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

export async function signOut() {
  const { error } = await supabase.auth.signOut()
  if (error) throw error
}

export async function signInWithEmail(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) throw error
  return data
}

export async function signUpWithEmail(email: string, password: string, fullName?: string) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { full_name: fullName } }
  })
  if (error) throw error
  return data
}

export async function signInWithOAuth(provider: 'google' | 'github' | 'discord') {
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: `${window.location.origin}/auth/callback` }
  })
  if (error) throw error
}

export async function signInWithPhone(phone: string) {
  const { error } = await supabase.auth.signInWithOtp({ phone })
  if (error) throw error
}

export async function verifyPhoneOtp(phone: string, token: string) {
  const { data, error } = await supabase.auth.verifyOtp({ phone, token, type: 'sms' })
  if (error) throw error
  return data
}
```

### `lib/supabase/server.ts`

```typescript
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {}
        },
      },
    }
  )
}
```

### `lib/supabase/middleware.ts`

```typescript
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          supabaseResponse = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  await supabase.auth.getUser()
  return supabaseResponse
}
```

---

## 4. Next.js Middleware

Create `middleware.ts` in project root:

```typescript
import { type NextRequest } from 'next/server'
import { updateSession } from '@/lib/supabase/middleware'

export async function middleware(request: NextRequest) {
  return await updateSession(request)
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)'],
}
```

---

## 5. OAuth Callback

Create `app/auth/callback/route.ts`:

```typescript
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/dashboard'

  if (code) {
    const supabase = await createClient()
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  return NextResponse.redirect(`${origin}/auth/signin?error=auth_failed`)
}
```

---

## 6. Auth Modal Component (ChatGPT Style)

### `components/auth/AuthModal.tsx`

```tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, Mail, Phone, Chrome, Github } from 'lucide-react'
import { FaDiscord } from 'react-icons/fa'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import {
  signInWithEmail,
  signUpWithEmail,
  signInWithOAuth,
  signInWithPhone,
  verifyPhoneOtp,
} from '@/lib/supabase/client'

interface AuthModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultTab?: 'signin' | 'signup'
  onSuccess?: () => void
}

export function AuthModal({ open, onOpenChange, defaultTab = 'signin', onSuccess }: AuthModalProps) {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  // Form states
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [showOtpInput, setShowOtpInput] = useState(false)

  const resetForm = () => {
    setEmail('')
    setPassword('')
    setFullName('')
    setPhone('')
    setOtp('')
    setError(null)
    setMessage(null)
    setShowOtpInput(false)
  }

  const handleSuccess = () => {
    resetForm()
    onOpenChange(false)
    onSuccess?.()
    router.refresh()
  }

  // Email Sign In
  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await signInWithEmail(email, password)
      handleSuccess()
    } catch (err: any) {
      setError(err.message || 'Sign in failed')
    } finally {
      setLoading(false)
    }
  }

  // Email Sign Up
  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await signUpWithEmail(email, password, fullName)
      setMessage('Check your email for a confirmation link!')
    } catch (err: any) {
      setError(err.message || 'Sign up failed')
    } finally {
      setLoading(false)
    }
  }

  // OAuth
  const handleOAuth = async (provider: 'google' | 'github' | 'discord') => {
    setLoading(true)
    setError(null)

    try {
      await signInWithOAuth(provider)
    } catch (err: any) {
      setError(err.message || 'OAuth failed')
      setLoading(false)
    }
  }

  // Phone OTP
  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await signInWithPhone(phone)
      setShowOtpInput(true)
      setMessage('OTP sent to your phone')
    } catch (err: any) {
      setError(err.message || 'Failed to send OTP')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await verifyPhoneOtp(phone, otp)
      handleSuccess()
    } catch (err: any) {
      setError(err.message || 'Invalid OTP')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) resetForm(); onOpenChange(isOpen) }}>
      <DialogContent className="sm:max-w-[400px] p-0 gap-0">
        <DialogHeader className="p-6 pb-0">
          <DialogTitle className="text-center text-xl">Welcome to Nurav AI</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue={defaultTab} className="w-full" onValueChange={() => { setError(null); setMessage(null) }}>
          <TabsList className="grid w-full grid-cols-2 mx-6 mt-4" style={{ width: 'calc(100% - 48px)' }}>
            <TabsTrigger value="signin">Sign In</TabsTrigger>
            <TabsTrigger value="signup">Sign Up</TabsTrigger>
          </TabsList>

          {/* Sign In Tab */}
          <TabsContent value="signin" className="p-6 pt-4 space-y-4">
            {/* OAuth Buttons */}
            <div className="space-y-2">
              <Button variant="outline" className="w-full" onClick={() => handleOAuth('google')} disabled={loading}>
                <Chrome className="mr-2 h-4 w-4" /> Continue with Google
              </Button>
              <Button variant="outline" className="w-full" onClick={() => handleOAuth('github')} disabled={loading}>
                <Github className="mr-2 h-4 w-4" /> Continue with GitHub
              </Button>
              <Button variant="outline" className="w-full" onClick={() => handleOAuth('discord')} disabled={loading}>
                <FaDiscord className="mr-2 h-4 w-4" /> Continue with Discord
              </Button>
            </div>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <Separator />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">or</span>
              </div>
            </div>

            {/* Email Form */}
            <form onSubmit={handleSignIn} className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="signin-email">Email</Label>
                <Input
                  id="signin-email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="signin-password">Password</Label>
                <Input
                  id="signin-password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
                Sign In with Email
              </Button>
            </form>
          </TabsContent>

          {/* Sign Up Tab */}
          <TabsContent value="signup" className="p-6 pt-4 space-y-4">
            {message ? (
              <div className="text-center py-4">
                <p className="text-sm text-muted-foreground">{message}</p>
                <Button variant="link" onClick={() => setMessage(null)}>Back to sign up</Button>
              </div>
            ) : (
              <>
                {/* OAuth Buttons */}
                <div className="space-y-2">
                  <Button variant="outline" className="w-full" onClick={() => handleOAuth('google')} disabled={loading}>
                    <Chrome className="mr-2 h-4 w-4" /> Continue with Google
                  </Button>
                  <Button variant="outline" className="w-full" onClick={() => handleOAuth('github')} disabled={loading}>
                    <Github className="mr-2 h-4 w-4" /> Continue with GitHub
                  </Button>
                </div>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <Separator />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">or</span>
                  </div>
                </div>

                {/* Email Sign Up Form */}
                <form onSubmit={handleSignUp} className="space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="signup-name">Full Name</Label>
                    <Input
                      id="signup-name"
                      type="text"
                      placeholder="John Doe"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-email">Email</Label>
                    <Input
                      id="signup-email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-password">Password</Label>
                    <Input
                      id="signup-password"
                      type="password"
                      placeholder="Min 6 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={6}
                    />
                  </div>

                  {error && <p className="text-sm text-destructive">{error}</p>}

                  <Button type="submit" className="w-full" disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Create Account
                  </Button>
                </form>
              </>
            )}
          </TabsContent>
        </Tabs>

        {/* Phone Auth Section */}
        <div className="p-6 pt-0">
          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center">
              <Separator />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">or use phone</span>
            </div>
          </div>

          {!showOtpInput ? (
            <form onSubmit={handleSendOtp} className="flex gap-2">
              <Input
                type="tel"
                placeholder="+1234567890"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                className="flex-1"
              />
              <Button type="submit" variant="outline" disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Phone className="h-4 w-4" />}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp} className="space-y-2">
              <p className="text-sm text-muted-foreground">Enter the code sent to {phone}</p>
              <div className="flex gap-2">
                <Input
                  type="text"
                  placeholder="000000"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  maxLength={6}
                  required
                  className="flex-1"
                />
                <Button type="submit" disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verify'}
                </Button>
              </div>
              <Button type="button" variant="link" size="sm" onClick={() => setShowOtpInput(false)}>
                Use different number
              </Button>
            </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

### `components/auth/index.ts`

```typescript
export { AuthModal } from './AuthModal'
```

---

## 7. API Client (Backend Calls)

### `lib/api.ts`

```typescript
import { supabase } from '@/lib/supabase/client'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function apiClient<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession()

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.detail || error.message)
  }

  return response.json()
}

// Helper methods
export const api = {
  get: <T = any>(endpoint: string) => apiClient<T>(endpoint),

  post: <T = any>(endpoint: string, data: any) =>
    apiClient<T>(endpoint, { method: 'POST', body: JSON.stringify(data) }),

  put: <T = any>(endpoint: string, data: any) =>
    apiClient<T>(endpoint, { method: 'PUT', body: JSON.stringify(data) }),

  delete: <T = any>(endpoint: string) =>
    apiClient<T>(endpoint, { method: 'DELETE' }),

  // Auth specific
  getCurrentUser: () => apiClient('/auth/me'),
}
```

---

## 8. Protected Layout

### `app/(protected)/layout.tsx`

```tsx
import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/')
  }

  return <>{children}</>
}
```

---

## 9. Required shadcn Components

Install these shadcn components:

```bash
npx shadcn@latest add dialog button input label tabs separator
```

Also install react-icons for Discord icon:

```bash
npm install react-icons
```

---

## 10. Backend API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/signup` | POST | No | Email signup |
| `/auth/signin` | POST | No | Email signin |
| `/auth/signout` | POST | No | Sign out |
| `/auth/refresh-token` | POST | No | Refresh token |
| `/auth/me` | GET | Yes | Get current user |
| `/auth/phone/send-otp` | POST | No | Send phone OTP |
| `/auth/phone/verify-otp` | POST | No | Verify OTP |

---

## 11. File Structure

```
your-frontend/
├── .env.local
├── middleware.ts
├── lib/
│   ├── api.ts
│   └── supabase/
│       ├── client.ts
│       ├── server.ts
│       └── middleware.ts
├── components/
│   ├── auth/
│   │   ├── AuthModal.tsx
│   │   └── index.ts
│   └── ui/          (shadcn components)
└── app/
    ├── auth/
    │   └── callback/
    │       └── route.ts
    └── (protected)/
        └── layout.tsx
```

---

## 12. Supabase Dashboard Setup

1. Go to **Authentication > Providers**
2. Enable: Email, Phone (with Twilio), Google, GitHub, Discord
3. Set **Site URL**: `http://localhost:3000`
4. Add **Redirect URL**: `http://localhost:3000/auth/callback`

---

## 13. Usage Example

Your Header component already handles auth state. The `AuthModal` integrates with it:

```tsx
import { AuthModal } from '@/components/auth'

// In your component:
const [authModalOpen, setAuthModalOpen] = useState(false)

<AuthModal
  open={authModalOpen}
  onOpenChange={setAuthModalOpen}
  defaultTab="signin"
  onSuccess={() => router.refresh()}
/>
```

---

## 14. Testing

1. Start backend: `python main.py`
2. Start frontend: `npm run dev`
3. Click "Sign In" or "Get Started" button
4. Test email/password, OAuth, or phone auth
5. After auth, call `api.getCurrentUser()` to verify
