# Frontend Integration Guide

Authentication with username requirement, password validation, Bloom filter username checking, and secure password hashing using shadcn/ui.

---

## Username Rules
- **Length**: 6-18 characters
- **Start**: Must start with a letter (a-z, A-Z)
- **Allowed**: Letters, numbers, `_`, `-`, `.`
- **Examples**: `varun_dev`, `john.doe123`, `alice-smith`

---

## Password Rules
- **Length**: 8-128 characters
- **Uppercase**: At least one uppercase letter (A-Z)
- **Lowercase**: At least one lowercase letter (a-z)
- **Number**: At least one digit (0-9)
- **Special**: At least one special character (!@#$%^&*...)
- **Patterns**: No sequential (123, abc) or repeated (aaa) patterns

---

## 1. Install Dependencies

```bash
npm install @supabase/supabase-js @supabase/ssr lucide-react
npx shadcn@latest add dialog button input label tabs separator
```

---

## 2. Environment Variables (`.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 3. API Client (`lib/api.ts`)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Type definitions
export interface UsernameCheckResponse {
  username: string;
  available: boolean;
  message: string;
  suggestions?: string[];
}

export interface PasswordValidationResponse {
  valid: boolean;
  score: number;
  level: 'weak' | 'fair' | 'good' | 'strong';
  issues: string[];
  feedback: string[];
}

export interface RandomUsernameResponse {
  username: string;
  suggestions: string[];
}

export interface AuthResponse {
  success: boolean;
  message: string;
  user?: { id: string; email: string; username?: string; };
  access_token?: string;
  refresh_token?: string;
}

export async function apiClient<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    mode: 'cors',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.detail || error.message);
  }

  return response.json();
}

export const api = {
  // Auth endpoints
  signup: (data: { email: string; password: string; username: string; full_name?: string }) =>
    apiClient<AuthResponse>('/auth/signup', { method: 'POST', body: JSON.stringify(data) }),

  signin: (data: { email: string; password: string }) =>
    apiClient<AuthResponse>('/auth/signin', { method: 'POST', body: JSON.stringify(data) }),

  signout: (token: string) =>
    apiClient('/auth/signout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } }),

  me: (token: string) =>
    apiClient('/auth/me', { headers: { Authorization: `Bearer ${token}` } }),

  // Username validation endpoints
  checkUsername: (username: string) =>
    apiClient<UsernameCheckResponse>(`/auth/check-username/${encodeURIComponent(username)}`),

  generateUsername: () =>
    apiClient<RandomUsernameResponse>('/auth/generate-username'),

  // Password validation endpoint
  validatePassword: (password: string) =>
    apiClient<PasswordValidationResponse>('/auth/validate-password', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
};
```

---

## 4. Supabase Client (`lib/supabase/client.ts`)

```typescript
import { createBrowserClient } from '@supabase/ssr';

export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// OAuth and Phone auth (signup/signin use backend API)
export async function signInWithOAuth(provider: 'google' | 'github' | 'discord') {
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: `${window.location.origin}/auth/callback` }
  });
  if (error) throw error;
}

export async function signInWithPhone(phone: string) {
  const { error } = await supabase.auth.signInWithOtp({ phone });
  if (error) throw error;
}

export async function verifyPhoneOtp(phone: string, token: string) {
  const { data, error } = await supabase.auth.verifyOtp({ phone, token, type: 'sms' });
  if (error) throw error;
  return data;
}

export async function signOut() {
  await supabase.auth.signOut();
}
```

---

## 5. Validation Utilities (`lib/validation.ts`)

```typescript
const USERNAME_REGEX = /^[a-zA-Z][a-zA-Z0-9_.\-]{5,17}$/;

export interface PasswordValidationResult {
  valid: boolean;
  score: number;
  level: 'weak' | 'fair' | 'good' | 'strong';
  issues: string[];
  feedback: string[];
}

export function validateUsername(username: string): { valid: boolean; error?: string } {
  if (!username) return { valid: false, error: 'Username is required' };
  if (username.length < 6) return { valid: false, error: 'Username must be at least 6 characters' };
  if (username.length > 18) return { valid: false, error: 'Username must be at most 18 characters' };
  if (!/^[a-zA-Z]/.test(username)) return { valid: false, error: 'Username must start with a letter' };
  if (!USERNAME_REGEX.test(username)) return { valid: false, error: 'Only letters, numbers, _, -, . allowed' };
  return { valid: true };
}

export function validatePassword(password: string): PasswordValidationResult {
  const issues: string[] = [];
  let score = 0;

  if (!password) return { valid: false, score: 0, level: 'weak', issues: ['Password is required'], feedback: [] };

  // Length checks
  if (password.length < 8) issues.push('At least 8 characters');
  else { score += 10; if (password.length >= 12) score += 10; if (password.length >= 16) score += 10; }

  // Character type checks
  if (!/[A-Z]/.test(password)) issues.push('One uppercase letter'); else score += 10;
  if (!/[a-z]/.test(password)) issues.push('One lowercase letter'); else score += 10;
  if (!/\d/.test(password)) issues.push('One number'); else score += 10;
  if (!/[!@#$%^&*()_+\-=\[\]{}|;':",./<>?]/.test(password)) issues.push('One special character'); else score += 10;

  // Pattern checks
  if (/(.)\1{2,}|(012|123|234|345|456|567|678|789)|(abc|bcd|cde)/i.test(password)) {
    issues.push('No sequential or repeated patterns');
    score -= 10;
  }

  score = Math.max(0, Math.min(100, score));
  const level = score >= 80 ? 'strong' : score >= 60 ? 'good' : score >= 40 ? 'fair' : 'weak';

  return { valid: issues.length === 0, score, level, issues, feedback: [] };
}

export function getPasswordStrengthColor(level: string): string {
  const colors = { weak: '#ef4444', fair: '#f97316', good: '#eab308', strong: '#22c55e' };
  return colors[level as keyof typeof colors] || colors.weak;
}
```

---

## 6. Backend API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/signup` | POST | No | Signup with email, password (hashed), username |
| `/auth/signin` | POST | No | Sign in with email, password |
| `/auth/signout` | POST | Yes | Sign out (updates auth_users_table) |
| `/auth/me` | GET | Yes | Get current user |
| `/auth/validate-password` | POST | No | Validate password strength and complexity |
| `/auth/check-username/{username}` | GET | No | Check username availability (Bloom filter + DB) |
| `/auth/check-username` | POST | No | Check username availability (POST version) |
| `/auth/generate-username` | GET | No | Generate random available username |
| `/auth/bloom-filter` | GET | No | Get Bloom filter data for client-side checks |
| `/auth/phone/send-otp` | POST | No | Send phone OTP |
| `/auth/phone/verify-otp` | POST | No | Verify OTP |

---

## 7. Password Hashing Algorithm

The backend uses a custom secure password hashing algorithm:

1. **HMAC with Pepper**: Password is first processed with HMAC-SHA256 using a secret pepper
2. **Custom Twist**: XOR operation with a derived key from bcrypt salt
3. **bcrypt Hashing**: Final hash with bcrypt (cost factor 12)
4. **Version Prefix**: Stored as `$nurav$v1$<bcrypt_hash>` for future upgrades

```python
# Hash structure: $nurav$v1$<bcrypt_hash>
# Example: $nurav$v1$$2b$12$...
```

---

## 8. Bloom Filter for Username Checking

The Bloom filter provides fast probabilistic username availability checks:

- **Size**: 100,000 bits (~12.5KB)
- **Hash Functions**: 7 (using SHA-256 with different seeds)
- **False Positive Rate**: ~1%
- **Refresh**: Every 5 minutes from database

### Client-Side Usage (Optional)

```typescript
// Fetch Bloom filter data
const filterData = await api.getBloomFilter();

// Client can implement local checking for instant feedback
// Final verification always done server-side
```

---

## 9. auth_users_table Fields

### Core Fields
| Column | Type | Description |
|--------|------|-------------|
| `idx` | SERIAL | Auto-increment ID |
| `user_uuid` | UUID | From Supabase Auth |
| `shard_num` | INT | 1-26 based on first letter of username |
| `username` | VARCHAR(18) | Unique, 6-18 chars |
| `email` | VARCHAR | User email |
| `name` | VARCHAR | Display name |
| `password_hash` | TEXT | Custom hashed password ($nurav$v1$...) |
| `user_info` | JSONB | Metadata |
| `subscription_status` | VARCHAR | free, hooray, pro, enterprise |
| `created_at` | TIMESTAMPTZ | Creation time |
| `updated_at` | TIMESTAMPTZ | Last update |
| `last_login_at` | TIMESTAMPTZ | Last login |
| `profile_image_url` | TEXT | Avatar URL |
| `is_verified` | BOOLEAN | Email verified |
| `payment_customer_id` | VARCHAR | Stripe ID |
| `auth_user_role` | VARCHAR | free, premium, admin |

### Optional Fields
```sql
ALTER TABLE auth_users_table ADD COLUMN IF NOT EXISTS
  password_hash TEXT,
  phone_number VARCHAR(20),
  bio VARCHAR(500),
  location VARCHAR(255),
  timezone VARCHAR(50),
  preferred_language VARCHAR(10) DEFAULT 'en',
  two_factor_enabled BOOLEAN DEFAULT FALSE,
  login_count INT DEFAULT 0;
```

---

## 10. File Structure

```
your-frontend/
├── .env.local
├── lib/
│   ├── api.ts                 # API client with all endpoints
│   ├── validation.ts          # Username & password validation
│   └── supabase/
│       └── client.ts          # Supabase client setup
├── components/
│   └── auth/
│       └── AuthModal.tsx      # Full auth modal with all features

your-backend/
├── main.py                    # FastAPI app with CORS
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── auth.py        # All auth endpoints
│   │   └── models/
│   │       └── auth.py        # Pydantic models
│   └── services/
│       ├── user_service.py    # User sync and validation
│       ├── password_service.py # Password hashing & validation
│       └── bloom_filter_service.py # Username Bloom filter
```

---

## 11. Auth Modal Features

The AuthModal component includes:

1. **Sign In Tab**
   - OAuth buttons (Google, GitHub, Discord)
   - Email/password form
   - Password visibility toggle

2. **Sign Up Tab**
   - OAuth buttons
   - Username field with:
     - Real-time validation
     - Debounced availability check (Bloom filter + DB)
     - Random username generator button
     - Suggestions when username is taken
   - Email field
   - Password field with:
     - Strength indicator bar (0-100)
     - Level indicator (weak/fair/good/strong)
     - Real-time validation feedback
     - Visibility toggle

3. **Phone Auth Section**
   - Phone number input
   - OTP verification

---

## 12. CORS Configuration

Backend CORS is configured to allow:
- Origins: localhost:3000, 127.0.0.1:3000, custom via FRONTEND_URL env
- Methods: GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD
- Headers: Content-Type, Authorization, Accept, etc.
- Credentials: Enabled
- Preflight cache: 24 hours

```python
# Additional origins via environment
ALLOWED_ORIGINS=https://your-domain.com,https://staging.your-domain.com
```
