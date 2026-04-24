import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
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
  const [messages, setMessages] = useState([
    {
      id: 0,
      role: 'bot',
      content: 'Здравствуйте! Я учебный ассистент кафедры компьютерной безопасности и технической экспертизы. Задайте вопрос по учебным материалам.',
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const question = input.trim()
    if (!question || loading) return

    const userMsg = { id: Date.now(), role: 'user', content: question }
    const botPlaceholder = { id: Date.now() + 1, role: 'bot', content: '', loading: true }

    setMessages(prev => [...prev, userMsg, botPlaceholder])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const data = await res.json()
      setMessages(prev =>
        prev.map(m => m.id === botPlaceholder.id
          ? { ...m, content: data.answer, loading: false }
          : m
        )
      )
    } catch {
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

  return (
    <div className="layout">
      <header className="header">
        <div className="header__logo">
          <ShieldIcon />
        </div>
        <div className="header__text">
          <h1 className="header__title">Учебный ассистент</h1>
          <p className="header__subtitle">Кафедра компьютерной безопасности и технической экспертизы</p>
        </div>
        <div className="header__badge">AI</div>
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
