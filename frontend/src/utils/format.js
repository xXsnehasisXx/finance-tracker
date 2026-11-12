export const CATEGORIES = ['food', 'transport', 'utilities', 'entertainment', 'health', 'salary', 'other']
export const BUDGET_CATEGORIES = CATEGORIES.filter((c) => c !== 'salary')
export const ACCOUNT_TYPES = ['savings', 'checking', 'credit']
export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })
export const formatINR = (n) => inr.format(Number(n || 0))
export const formatPercent = (n) => `${Number(n || 0).toFixed(1)}%`
export const titleCase = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '')

export const formatDate = (iso) => {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export const utilizationTone = (pct) => (pct >= 100 ? 'danger' : pct >= 80 ? 'warn' : 'ok')

// Same colours everywhere for a category
export const CATEGORY_COLORS = {
  food: '#f97316', transport: '#3b82f6', utilities: '#8b5cf6', entertainment: '#ec4899',
  health: '#10b981', salary: '#14b8a6', other: '#64748b',
}
