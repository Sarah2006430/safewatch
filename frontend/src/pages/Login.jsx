import { useState } from 'react'
import { ArrowRight, Radar } from 'lucide-react'
import ThemeToggle from '../components/ThemeToggle'
import { Button, Field, inputCls } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { INCIDENT_TYPES } from '../lib/constants'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function SignIn({ onSwitch }) {
  const { login } = useAuth()
  const [ident, setIdent] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try { await login(ident.trim(), password) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit}>
      <div className="label">Restricted system</div>
      <h2 className="num mt-1 text-4xl uppercase">Sign in</h2>
      <p className="mt-2 text-sm text-slate-400">Use your e-mail address or username.</p>
      <div className="mt-7 space-y-4">
        <Field label="E-mail or username"><input className={inputCls} value={ident} onChange={(e) => setIdent(e.target.value)} autoFocus autoComplete="username" /></Field>
        <Field label="Password"><input type="password" className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></Field>
        {error && <div className="border-l-2 border-[var(--color-alert)] bg-[var(--color-alert)]/10 px-3 py-2 text-sm text-[var(--color-alert)]">{error}</div>}
        <Button className="w-full py-3" disabled={busy || !ident || !password}>
          {busy ? 'Authenticating…' : <>Enter console <ArrowRight size={16} /></>}
        </Button>
      </div>
      <p className="mt-6 text-sm text-slate-400">
        New here? <button type="button" onClick={onSwitch} className="font-semibold text-[var(--color-signal)] hover:underline">Create an account</button>
      </p>
    </form>
  )
}

function SignUp({ onSwitch }) {
  const { signup } = useAuth()
  const [f, setF] = useState({ name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const problems = []
  if (f.name && f.name.trim().length < 2) problems.push('Enter your full name')
  if (f.email && !EMAIL_RE.test(f.email.trim())) problems.push('Enter a valid e-mail address')
  if (f.password && f.password.length < 8) problems.push('Password must be at least 8 characters')
  if (f.confirm && f.confirm !== f.password) problems.push('Passwords do not match')
  const ready = f.name && f.email && f.password && f.confirm && !problems.length

  const submit = async (e) => {
    e.preventDefault()
    if (!ready) return
    setBusy(true)
    setError('')
    try { await signup(f.name.trim(), f.email.trim(), f.password) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit}>
      <div className="label">Operator registration</div>
      <h2 className="num mt-1 text-4xl uppercase">Create account</h2>
      <p className="mt-2 text-sm text-slate-400">New accounts join the control room as operators.</p>
      <div className="mt-7 space-y-4">
        <Field label="Full name"><input className={inputCls} value={f.name} onChange={set('name')} autoFocus autoComplete="name" /></Field>
        <Field label="E-mail"><input type="email" className={inputCls} value={f.email} onChange={set('email')} autoComplete="email" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Password"><input type="password" className={inputCls} value={f.password} onChange={set('password')} autoComplete="new-password" /></Field>
          <Field label="Confirm password"><input type="password" className={inputCls} value={f.confirm} onChange={set('confirm')} autoComplete="new-password" /></Field>
        </div>
        {!!problems.length && <ul className="space-y-0.5 text-xs text-[var(--color-warn)]">{problems.map((p) => <li key={p}>• {p}</li>)}</ul>}
        {error && <div className="border-l-2 border-[var(--color-alert)] bg-[var(--color-alert)]/10 px-3 py-2 text-sm text-[var(--color-alert)]">{error}</div>}
        <Button className="w-full py-3" disabled={busy || !ready}>
          {busy ? 'Creating account…' : <>Create account <ArrowRight size={16} /></>}
        </Button>
      </div>
      <p className="mt-6 text-sm text-slate-400">
        Already registered? <button type="button" onClick={onSwitch} className="font-semibold text-[var(--color-signal)] hover:underline">Sign in</button>
      </p>
    </form>
  )
}

export default function Login() {
  const [mode, setMode] = useState('signin')

  return (
    <div className="console-bg relative grid h-full overflow-y-auto lg:grid-cols-[1.2fr_1fr]">
      <ThemeToggle className="absolute right-5 top-5 z-10" />
      <div className="relative hidden overflow-hidden border-r border-slate-800 lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="pointer-events-none absolute -left-40 top-1/2 h-[42rem] w-[42rem] -translate-y-1/2 rounded-full border border-slate-700" />
        <div className="pointer-events-none absolute -left-20 top-1/2 h-[30rem] w-[30rem] -translate-y-1/2 rounded-full border border-slate-700" />
        <div className="pointer-events-none absolute left-0 top-1/2 h-[18rem] w-[18rem] -translate-y-1/2 rounded-full border border-[var(--color-signal)]/40" />
        <div className="relative flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center bg-[var(--color-alert)] text-white"><Radar size={24} strokeWidth={2.4} /></div>
          <div className="num text-2xl tracking-wide">SAFEWATCH</div>
        </div>
        <div className="relative max-w-xl">
          <div className="label">Public safety operations</div>
          <h1 className="num mt-3 text-6xl uppercase leading-[.95]">
            See it first.<br /><span className="text-[var(--color-signal)]">Send help faster.</span>
          </h1>
          <p className="mt-5 max-w-md text-[15px] leading-relaxed text-slate-400">
            Computer vision watches CCTV and IP cameras around the clock. Every alert arrives with its location and video evidence,
            an operator confirms it, and the nearest police, medical, fire and rescue units are dispatched.
          </p>
        </div>
        <div className="relative grid grid-cols-5 border border-slate-700 bg-slate-900/60">
          {Object.values(INCIDENT_TYPES).map((m) => (
            <div key={m.short} className="border-r border-slate-700 p-3 last:border-0">
              <div style={{ color: m.color }}>{m.Icon && <m.Icon size={20} />}</div>
              <div className="mono mt-2 text-[10px] uppercase tracking-wider text-slate-400">{m.short}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="lift w-full max-w-sm border border-slate-800 bg-slate-900 p-7">
          <div className="mb-6 lg:hidden"><div className="num text-3xl">SAFEWATCH</div></div>
          {mode === 'signin'
            ? <SignIn onSwitch={() => setMode('signup')} />
            : <SignUp onSwitch={() => setMode('signin')} />}
          <p className="mono mt-6 border-t border-slate-800 pt-4 text-[10px] uppercase tracking-wider text-slate-500">All sign-ins are logged</p>
        </div>
      </div>
    </div>
  )
}
