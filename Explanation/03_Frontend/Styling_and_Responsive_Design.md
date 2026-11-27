# Styling and Responsive Design

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Source: [`frontend/src/styles/index.css`](../../frontend/src/styles/index.css) (107 lines, imported once in `main.jsx`). No CSS framework, CSS-in-JS, CSS modules or Material UI; the stylesheet is hand-written, global, class-based.

## 1. Design tokens (CSS variables)

```css
:root { --bg:#f4f6fb; --panel:#fff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0;
        --primary:#4f46e5; --primary-dark:#4338ca; --green:#16a34a; --orange:#f59e0b; --red:#dc2626;
        --radius:12px; --sidebar:240px; }
```

Semantic colours are used consistently: green = income/ok, orange = warning (80–99 %), red = expense/danger (≥ 100 %), indigo = primary actions.

## 2. Organisation of the stylesheet

The file is divided by comment banners:

| Section | Classes (examples) |
|---|---|
| base | `*{box-sizing}`, `body` (Inter/system font stack), headings, `.muted`, `.small`, `.pos`, `.neg`, `.num` (tabular numerals, right aligned) |
| layout | `.shell`, `.sidebar`, `.brand`, `.nav-link(.active)`, `.main`, `.topbar`, `.content` (max-width 1280px), `.scrim`, `.page-head` |
| cards & grids | `.card`, `.card-header`, `.stats`, `.stat(-good/-bad)`, `.grid-2`, `.grid-tx`, `.cards`, `.account-card` |
| buttons & forms | `.btn(-primary/-ghost/-block)`, `.btn-row`, `.link-btn`, `.icon-btn`, `.field(-error)`, `.field-label/-hint/-msg`, `.form-row`, `.form-actions`, `.form-error`, `.banner(-warn)`, `.filters`, `.period` |
| tables | `.table-wrap` (horizontal scroll), `.table`, `.pagination`, `.badge(-red/-green/-neutral/-savings/-checking/-credit)`, `.dot(-category)` |
| budgets | `.budget(-ok/-warn/-danger)`, `.progress`, `.progress-fill`, `.progress-ok/-warn/-danger`, `.alerts`, `.alert-red/-orange`, `.rank` |
| states | `.spinner(-wrap)` (CSS keyframes `spin`), `.empty`, `.error-state`, `.toasts/.toast(-success/-error)`, `.modal(-backdrop/-header)` |
| auth | `.auth-page` (gradient background), `.auth-card` |
| responsive | two media queries (below) |

Components pick classes dynamically, e.g. `` `budget budget-${tone}` ``, `` `dot dot-${category}` ``, `` `badge badge-${account_type}` ``.

## 3. Responsive behaviour

```css
@media (max-width: 1000px) { .grid-2, .grid-tx { grid-template-columns: 1fr; } }
@media (max-width: 800px) {
  .sidebar { transform: translateX(-100%); } .sidebar.open { transform: none; }
  .main { margin-left: 0; } .menu-btn { display: inline-block; }
  .scrim { display: block; position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 20; }
  .content { padding: 1rem; } .form-row { grid-template-columns: 1fr; } .stat-value { font-size: 1.2rem; }
}
```

| Breakpoint | Layout change |
|---|---|
| > 1000 px | fixed 240 px sidebar; two-column card grids (`.grid-2`), transactions grid 2fr/1fr |
| ≤ 1000 px | all multi-column grids collapse to one column |
| ≤ 800 px | sidebar becomes an off-canvas drawer toggled by the hamburger (`AppLayout` state), scrim overlay, content padding reduced, two-field form rows stack |

Fluid techniques used throughout: `grid-template-columns: repeat(auto-fit, minmax(190px, 1fr))` (KPI tiles), `repeat(auto-fill, minmax(260px, 1fr))` (account cards), `minmax(150px, 1fr)` (filter bar), `min-width: 0` on cards to let charts shrink, `.table-wrap { overflow-x: auto }` so wide tables scroll horizontally on phones, `flex-wrap` on header/button rows, `max-width: 100%` modals with `max-height: 92vh; overflow: auto`.

`index.html` includes `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.

## 4. Currency and number display

All amounts are displayed through `formatINR` (`Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits: 2})`) → `₹1,23,456.00` (Indian digit grouping). Form labels carry "(₹)". The backend stores a `currency` per account (default INR) but the UI always formats as INR.

## 5. Not present

Dark mode, theming switch, print styles, RTL support, animations beyond the spinner (the sidebar has `transition: none`), icon library (emoji are used as icons).
