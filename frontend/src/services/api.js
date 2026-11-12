const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const TOKEN_KEY = 'ft_token'

let token = localStorage.getItem(TOKEN_KEY)
let onUnauthorized = () => {}

export const setToken = (t) => {
  token = t
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}
export const getToken = () => token
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

function describe(detail) {
  if (Array.isArray(detail)) {
    return detail.map((e) => `${(e.loc || []).filter((p) => p !== 'body').join('.')}: ${e.msg}`).join('; ')
  }
  return typeof detail === 'string' ? detail : 'Request failed'
}

async function request(path, { method = 'GET', body, form, params, auth = true } = {}) {
  const url = new URL(BASE + path, window.location.origin)
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
  })
  const headers = {}
  let payload
  if (form) payload = new URLSearchParams(form)
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (auth && token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(url, { method, headers, body: payload })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running?')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && auth) onUnauthorized()
    throw new ApiError(res.status, describe(data?.detail))
  }
  return data
}

export const api = {
  register: (body) => request('/auth/register', { method: 'POST', body, auth: false }),
  login: (email, password) => request('/auth/login', { method: 'POST', form: { username: email, password }, auth: false }),
  me: () => request('/users/me'),
  updateMe: (body) => request('/users/me', { method: 'PATCH', body }),

  accounts: () => request('/accounts'),
  createAccount: (body) => request('/accounts', { method: 'POST', body }),
  renameAccount: (id, account_name) => request(`/accounts/${id}`, { method: 'PATCH', body: { account_name } }),
  deleteAccount: (id) => request(`/accounts/${id}`, { method: 'DELETE' }),
  accountSummary: (id) => request(`/accounts/${id}/summary`),

  transactions: (params) => request('/transactions', { params }),
  createTransaction: (body) => request('/transactions', { method: 'POST', body }),
  createTransfer: (body) => request('/transfers', { method: 'POST', body }),

  budgets: (params) => request('/budgets', { params }),
  createBudget: (body) => request('/budgets', { method: 'POST', body }),
  deleteBudget: (id) => request(`/budgets/${id}`, { method: 'DELETE' }),
  budgetAlerts: (params) => request('/budget-alerts', { params }),

  dashboard: (params) => request('/dashboard', { params }),
  spendingByCategory: (params) => request('/analytics/spending-by-category', { params }),
  incomeVsExpense: (params) => request('/analytics/income-vs-expense', { params }),
}
