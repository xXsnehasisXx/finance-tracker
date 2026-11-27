import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import ForumRounded from '@mui/icons-material/ForumRounded'
import InfoOutlined from '@mui/icons-material/InfoOutlined'
import OpenInNewRounded from '@mui/icons-material/OpenInNewRounded'
import SmartToyRounded from '@mui/icons-material/SmartToyRounded'
import Alert from '@mui/material/Alert'
import { PageHeader, SectionCard } from '../components/ui.jsx'

const FAQ_URL = import.meta.env.VITE_FAQ_URL || 'http://localhost:8501'
const ASSISTANT_URL = import.meta.env.VITE_ASSISTANT_URL || 'http://localhost:8502'

function AssistantCard({ icon, title, href, cta, children }) {
  return (
    <SectionCard sx={{ height: '100%' }}>
      <Stack spacing={2} sx={{ height: '100%', alignItems: 'flex-start' }}>
        <Box aria-hidden="true" sx={{ width: 44, height: 44, borderRadius: 3, display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText' }}>{icon}</Box>
        <Typography variant="h4" component="h2">{title}</Typography>
        <Typography color="text.secondary" sx={{ flexGrow: 1 }}>{children}</Typography>
        <Button variant="contained" component="a" href={href} target="_blank" rel="noreferrer" endIcon={<OpenInNewRounded />}>{cta}</Button>
      </Stack>
    </SectionCard>
  )
}

// The AI components run as separate Streamlit apps; this page is the entry point from the dashboard.
export default function Assistant() {
  return (
    <>
      <PageHeader title="AI Assistant" subtitle="Ask questions and get guidance from your own data" />
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' }, mb: 3 }}>
        <AssistantCard icon={<ForumRounded />} title="Finance FAQ & live data assistant" href={FAQ_URL} cta="Open FAQ assistant">
          Ask how the app works ("How do I set a monthly budget?") or about your live spending ("Am I over budget on food this month?"). Answers use the user manual and your own data.
        </AssistantCard>
        <AssistantCard icon={<SmartToyRounded />} title="Conversational assistant & financial health report" href={ASSISTANT_URL} cta="Open assistant">
          Add transactions in plain language ("Add a ₹500 grocery expense for today") with a confirmation step, and generate a multi-agent financial health report.
        </AssistantCard>
      </Box>
      <Alert severity="info" icon={<InfoOutlined />}>
        These assistants run separately (Streamlit). Start them as described in the README. They sign in with your own account and only see your data.
      </Alert>
    </>
  )
}
