import { Card } from '../components/ui.jsx'

const FAQ_URL = import.meta.env.VITE_FAQ_URL || 'http://localhost:8501'
const ASSISTANT_URL = import.meta.env.VITE_ASSISTANT_URL || 'http://localhost:8502'

// The AI components run as separate Streamlit apps; this page is the entry point from the dashboard.
export default function Assistant() {
  return (
    <>
      <div className="page-head"><h1>AI Assistant</h1></div>
      <div className="cards">
        <Card title="💬 Finance FAQ & live data assistant">
          <p>Ask how the app works ("How do I set a monthly budget?") or about your live spending ("Am I over budget on food this month?"). Answers use the user manual and your own data.</p>
          <a className="btn btn-primary" href={FAQ_URL} target="_blank" rel="noreferrer">Open FAQ assistant</a>
        </Card>
        <Card title="🤖 Conversational assistant & financial health report">
          <p>Add transactions in plain language ("Add a ₹500 grocery expense for today") with a confirmation step, and generate a multi-agent financial health report.</p>
          <a className="btn btn-primary" href={ASSISTANT_URL} target="_blank" rel="noreferrer">Open assistant</a>
        </Card>
      </div>
      <p className="muted small">These assistants run separately (Streamlit). Start them as described in the README. They sign in with your own account and only see your data.</p>
    </>
  )
}
