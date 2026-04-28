import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import Auth from './Auth.jsx'
import Admin from './Admin.jsx'
import './App.css'

const ShieldIcon = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z"/>
    <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const SendIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
)

const BotIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="11" width="18" height="10" rx="2"/>
    <circle cx="12" cy="5" r="2"/>
    <line x1="12" y1="7" x2="12" y2="11"/>
    <line x1="8" y1="16" x2="8" y2="16" strokeWidth="2" strokeLinecap="round"/>
    <line x1="12" y1="16" x2="12" y2="16" strokeWidth="2" strokeLinecap="round"/>
    <line x1="16" y1="16" x2="16" y2="16" strokeWidth="2" strokeLinecap="round"/>
  </svg>
)

const UserIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="8" r="4"/>
    <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
  </svg>
)

const LogoutIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
)

function TypingDots() {
  return (
    <div className="typing-dots">
      <span/><span/><span/>
    </div>
  )
}

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`message ${isUser ? 'message--user' : 'message--bot'}`}>
      <div className="message__avatar">
        {isUser ? <UserIcon /> : <BotIcon />}
      </div>
      <div className="message__bubble">
        {msg.loading ? (
          <TypingDots />
        ) : (
          <ReactMarkdown>{msg.content}</ReactMarkdown>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user')
    return saved ? JSON.parse(saved) : null
  })
  const [page, setPage] = useState(() => localStorage.getItem('page') || 'chat')

  const [messages, setMessages] = useState([
    {
      id: 0,
      role: 'bot',
      content: 'Здравствуйте! Я учебный ассистент кафедры компьютерной безопасности и экспертизы. Задайте вопрос по учебным материалам.',
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState('qwen2.5:3b')
  const [models, setModels] = useState([])
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    // Загрузим список моделей
    fetch('/models')
      .then(res => res.json())
      .then(data => setModels(data.models))
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const navigate = (p) => {
    setPage(p)
    localStorage.setItem('page', p)
  }

  const handleLogin = (data) => {
    const u = { username: data.username, full_name: data.full_name, group_number: data.group_number, role: data.role }
    setUser(u)
    navigate(data.role === 'admin' ? 'admin' : 'chat')
  }

  const handleLogout = async () => {
    const token = localStorage.getItem('token')
    if (token) {
      await fetch('/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    }
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('page')
    setUser(null)
    navigate('chat')
    setMessages([{
      id: 0,
      role: 'bot',
      content: 'Здравствуйте! Я учебный ассистент кафедры компьютерной безопасности и технической экспертизы. Задайте вопрос по учебным материалам.',
    }])
  }

  const send = async () => {
    const question = input.trim()
    if (!question || loading) return

    const token = localStorage.getItem('token')
    const userMsg = { id: Date.now(), role: 'user', content: question }
    const botPlaceholder = { id: Date.now() + 1, role: 'bot', content: '', loading: true }

    setMessages(prev => [...prev, userMsg, botPlaceholder])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ question, model: selectedModel, stream: true }),
      })
      
      if (res.status === 401) {
        handleLogout()
        return
      }

      if (!res.ok) {
        throw new Error('Network response was not ok')
      }

      // Обработка потока SSE
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulatedText = ''
      let buffer = ''

      // Убираем индикатор загрузки
      setMessages(prev =>
        prev.map(m => m.id === botPlaceholder.id
          ? { ...m, loading: false }
          : m
        )
      )

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // Декодируем чанк и добавляем к буферу
        buffer += decoder.decode(value, { stream: true })
        
        // Разбиваем буфер на строки
        const lines = buffer.split('\n')
        
        // Последняя строка может быть неполной, сохраняем её в буфер
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6).trim()
              if (!jsonStr) continue
              
              const data = JSON.parse(jsonStr)
              
              if (data.error) {
                setMessages(prev =>
                  prev.map(m => m.id === botPlaceholder.id
                    ? { ...m, content: 'Ошибка: ' + data.error, loading: false }
                    : m
                  )
                )
                return
              }

              if (data.token) {
                accumulatedText += data.token
                setMessages(prev =>
                  prev.map(m => m.id === botPlaceholder.id
                    ? { ...m, content: accumulatedText, loading: false }
                    : m
                  )
                )
              }

              if (data.done) {
                return
              }
            } catch (e) {
              console.error('Parse error:', e, 'Line:', line)
            }
          }
        }
      }

    } catch (error) {
      setMessages(prev =>
        prev.map(m => m.id === botPlaceholder.id
          ? { ...m, content: 'Ошибка соединения с сервером.', loading: false }
          : m
        )
      )
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (!user) return <Auth onLogin={handleLogin} />
  if (user.role === 'admin' && page === 'admin') return <Admin token={localStorage.getItem('token')} onBack={() => navigate('chat')} />

  return (
    <div className="layout">
      <header className="header">
        <div className="header__logo">
          <ShieldIcon />
        </div>
        <div className="header__text">
          <h1 className="header__title">Учебный ассистент</h1>
          <p className="header__subtitle">Кафедра компьютерной безопасности и экспертизы</p>
        </div>
        {user.role === 'admin' && (
          <button className="header__nav-btn" onClick={() => navigate('admin')}>
            Панель админа
          </button>
        )}
        <div className="header__user">
          <span className="header__user-name">{user.full_name}</span>
          <span className="header__user-group">{user.role === 'admin' ? 'Администратор' : `Группа ${user.group_number}`}</span>
        </div>
        <button className="header__logout" onClick={handleLogout} title="Выйти">
          <LogoutIcon />
        </button>
      </header>

      <main className="chat">
        <div className="chat__messages">
          {messages.map(msg => (
            <Message key={msg.id} msg={msg} />
          ))}
          <div ref={bottomRef} />
        </div>
      </main>

      <footer className="input-area">
        {models.length > 0 && (
          <div className="model-selector">
            <label htmlFor="model-select" className="model-selector__label">
              Модель:
            </label>
            <select
              id="model-select"
              className="model-selector__select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={loading}
            >
              {models.map(model => (
                <option key={model.id} value={model.id}>
                  {model.name} — {model.description}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="input-wrap">
          <textarea
            ref={inputRef}
            className="input-wrap__field"
            placeholder="Задайте вопрос по учебным материалам..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            disabled={loading}
          />
          <button
            className={`input-wrap__btn ${loading ? 'input-wrap__btn--loading' : ''}`}
            onClick={send}
            disabled={loading || !input.trim()}
            aria-label="Отправить"
          >
            <SendIcon />
          </button>
        </div>
        <p className="input-area__hint">Enter — отправить · Shift+Enter — новая строка</p>
      </footer>
    </div>
  )
}
