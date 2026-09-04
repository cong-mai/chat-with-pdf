import { useEffect, useState } from 'react'
import { listUsers, setUserActive } from '../api.js'

export default function AdminPanel({ token, onAuthError }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    refresh()
  }, [])

  async function refresh() {
    setLoading(true)
    try {
      const data = await listUsers(token)
      setUsers(data.users)
      setError('')
    } catch (err) {
      if (onAuthError(err)) return
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleToggle(u) {
    setBusyId(u.id)
    setError('')
    try {
      await setUserActive(u.id, !u.active, token)
      await refresh()
    } catch (err) {
      if (onAuthError(err)) return
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="admin-panel" aria-label="Admin">
      <h2 className="admin-title">Users</h2>
      {error && (
        <p className="status" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="status">Loading…</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>{u.active ? 'Active' : 'Deactivated'}</td>
                <td>{new Date(u.created_at).toLocaleDateString()}</td>
                <td>
                  <button type="button" onClick={() => handleToggle(u)} disabled={busyId === u.id}>
                    {u.active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
