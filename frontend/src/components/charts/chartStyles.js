// Shared Recharts styling derived from the active MUI theme so charts follow dark/light mode.
export const chartTooltipStyles = (theme) => ({
  contentStyle: {
    backgroundColor: theme.palette.background.paper,
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: theme.shape.borderRadius,
    color: theme.palette.text.primary,
    boxShadow: theme.palette.mode === 'dark' ? 'none' : '0 4px 16px rgba(28, 25, 23, 0.12)',
  },
  labelStyle: { color: theme.palette.text.primary, fontWeight: 600 },
  itemStyle: { color: theme.palette.text.primary },
  cursor: { fill: theme.palette.action.hover },
})
