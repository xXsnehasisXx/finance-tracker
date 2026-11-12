import { formatDate, formatINR, titleCase } from '../utils/format.js'

export default function TransactionTable({ items, accountNames }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr><th>Date</th><th>Description</th><th>Category</th><th>Merchant</th><th>Account</th><th className="num">Amount</th><th>Type</th></tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.id}>
              <td>{formatDate(t.transaction_date)}</td>
              <td>{t.description}{t.is_transfer && <span className="badge badge-neutral">transfer</span>}</td>
              <td><span className={`dot dot-${t.category}`} />{titleCase(t.category)}</td>
              <td>{t.merchant || '—'}</td>
              <td>{accountNames?.[t.account_id] || `#${t.account_id}`}</td>
              <td className={`num ${t.type === 'debit' ? 'neg' : 'pos'}`}>{t.type === 'debit' ? '−' : '+'}{formatINR(t.amount)}</td>
              <td><span className={`badge ${t.type === 'debit' ? 'badge-red' : 'badge-green'}`}>{t.type}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
