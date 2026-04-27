import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './Admin.css'

const BackIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="15 18 9 12 15 6"/>
  </svg>
)

const UserIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="8" r="4"/>
    <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
  </svg>
)

function formatDate(iso) {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

export default function Admin({ token, onBack }) {
  const [users, setUsers] = useState([])
  const [selectedUser, setSelectedUser] = useState(null)
  const [chats, setChats] = useState([])
  const [loadingChats, setLoadingChats] = useState(false)

  useEffect(() => {
    fetch('/admin/users', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(setUsers)
  }, [token])

  const openUser = async (user) => {
    setSelectedUser(user)
    setLoadingChats(true)
    const res = await fetch(`/admin/users/${user.id}/chats`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = await res.json()
    setChats(data)
    setLoadingChats(false)
  }

  return (
    <div className="admin">
      <header className="admin__header">
        <button className="admin__back" onClick={onBack}>
          <BackIcon /> К чату
        </button>
        <h1 className="admin__title">Панель администратора</h1>
        <span className="admin__badge">ADMIN</span>
      </header>

      <div className="admin__body">
        {/* Список пользователей */}
        <aside className="admin__sidebar">
          <h2 className="admin__sidebar-title">Курсанты ({users.length})</h2>
          <div className="admin__user-list">
            {users.length === 0 && (
              <p className="admin__empty">Нет зарегистрированных курсантов</p>
            )}
            {users.map(u => (
              <button
                key={u.id}
                className={`admin__user-item ${selectedUser?.id === u.id ? 'admin__user-item--active' : ''}`}
                onClick={() => openUser(u)}
              >
                <div className="admin__user-avatar"><UserIcon /></div>
                <div className="admin__user-info">
                  <span className="admin__user-name">{u.full_name}</span>
                  <span className="admin__user-meta">Группа {u.group_number} · {u.username}</span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Переписка */}
        <main className="admin__chat">
          {!selectedUser ? (
            <div className="admin__placeholder">
              <p>Выберите курсанта чтобы просмотреть переписку</p>
            </div>
          ) : (
            <>
              <div className="admin__chat-header">
                <strong>{selectedUser.full_name}</strong>
                <span>Группа {selectedUser.group_number} · {selectedUser.username}</span>
                <span>Зарегистрирован: {formatDate(selectedUser.created_at)}</span>
              </div>
              <div className="admin__chat-messages">
                {loadingChats && <p className="admin__empty">Загрузка...</p>}
                {!loadingChats && chats.length === 0 && (
                  <p className="admin__empty">Переписки нет</p>
                )}
                {chats.map((c, i) => (
                  <div key={i} className="admin__chat-pair">
                    <div className="admin__msg admin__msg--user">
                      <span className="admin__msg-label">Вопрос</span>
                      <p>{c.question}</p>
                      <span className="admin__msg-time">{formatDate(c.created_at)}</span>
                    </div>
                    <div className="admin__msg admin__msg--bot">
                      <span className="admin__msg-label">Ответ</span>
                      <ReactMarkdown>{c.answer}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
