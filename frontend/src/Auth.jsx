import { useState } from 'react'
import './Auth.css'

const ShieldIcon = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z"/>
    <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

export default function Auth({ onLogin }) {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [form, setForm] = useState({ username: '', password: '', full_name: '', group_number: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (mode === 'register') {
        const res = await fetch('/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
        const data = await res.json()
        if (!res.ok) { setError(data.detail); return }
        setMode('login')
        setForm({ ...form, full_name: '', group_number: '' })
        setError('')
      } else {
        const res = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: form.username, password: form.password }),
        })
        const data = await res.json()
        if (!res.ok) { setError(data.detail); return }
        localStorage.setItem('token', data.token)
        localStorage.setItem('user', JSON.stringify({
          username: data.username,
          full_name: data.full_name,
          group_number: data.group_number,
        }))
        onLogin(data)
      }
    } catch {
      setError('Ошибка соединения с сервером')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card__header">
          <div className="auth-card__icon"><ShieldIcon /></div>
          <h1 className="auth-card__title">Учебный ассистент</h1>
          <p className="auth-card__subtitle">Кафедра компьютерной безопасности и технической экспертизы</p>
        </div>

        <div className="auth-tabs">
          <button
            className={`auth-tabs__btn ${mode === 'login' ? 'auth-tabs__btn--active' : ''}`}
            onClick={() => { setMode('login'); setError('') }}
          >Вход</button>
          <button
            className={`auth-tabs__btn ${mode === 'register' ? 'auth-tabs__btn--active' : ''}`}
            onClick={() => { setMode('register'); setError('') }}
          >Регистрация</button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && (
            <>
              <div className="auth-form__field">
                <label>ФИО</label>
                <input
                  type="text"
                  placeholder="Иванов Иван Иванович"
                  value={form.full_name}
                  onChange={update('full_name')}
                  required
                />
              </div>
              <div className="auth-form__field">
                <label>Номер группы</label>
                <input
                  type="text"
                  placeholder="КБ-101"
                  value={form.group_number}
                  onChange={update('group_number')}
                  required
                />
              </div>
            </>
          )}

          <div className="auth-form__field">
            <label>Логин</label>
            <input
              type="text"
              placeholder="ivan123"
              value={form.username}
              onChange={update('username')}
              required
            />
          </div>

          <div className="auth-form__field">
            <label>Пароль</label>
            <input
              type="password"
              placeholder="••••••••"
              value={form.password}
              onChange={update('password')}
              required
            />
          </div>

          {error && <p className="auth-form__error">{error}</p>}

          <button className="auth-form__submit" type="submit" disabled={loading}>
            {loading ? 'Загрузка...' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
          </button>
        </form>
      </div>
    </div>
  )
}
