# Control Tower — Frontend

React + TypeScript + Vite dashboard for the supply-chain analytics API.

## Quick start

```bash
npm install
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000`, so the backend must be
running. Start it from the `backend` folder:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

## Scripts

| Command | Purpose |
| :--- | :--- |
| `npm run dev` | Dev server with HMR on port 5173 |
| `npm run build` | Type-check (`tsc -b`) then produce a production bundle |
| `npm run preview` | Serve the built bundle locally |
| `npm run lint` | ESLint with TypeScript, React Hooks and jsx-a11y rules |

## Configuration

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `VITE_API_URL` | *(empty)* | Leave unset to use same-origin `/api` (the dev proxy in development, and the deployed origin in production). Set it only when the API lives on a different host. |

## Architecture

```
src/
├── components/
│   ├── ui/            Design-system primitives (Button, Card, Table, Toast…)
│   ├── layout/        AppShell, sidebar navigation, topbar
│   ├── charts/        Shared Recharts theme, tooltip and card frame
│   └── ErrorBoundary.tsx
├── features/
│   ├── dashboard/     Risk table, demand & signal charts, brief, simulation
│   └── forecast/      Forecast form and result panels
├── pages/             DashboardPage, ForecastPage (both lazy-loaded)
├── providers/         Theme (light/dark/system) and toast notifications
├── hooks/             useAsyncData — request state with abort-on-unmount
├── lib/               API client, class-name merge, formatters
└── types.ts           Response types mirroring backend/app/schemas.py
```

### Design system

All colour, spacing, radius, shadow and typography values are tokens defined
once in `src/index.css` and exposed through `tailwind.config.js`. Colours resolve
to `rgb(var(--token) / <alpha-value>)`, so utilities such as `bg-accent/10`
compose opacity correctly and a single `class="dark"` on `<html>` repaints the
whole product — including charts, since SVG honours CSS variables.

Never hardcode a hex value in a component. Use the semantic tokens:
`surface`, `surface-raised`, `surface-sunken`, `border`, `content`,
`content-muted`, `content-subtle`, `accent`, `brand`, `ok`, `warn`, `danger`,
`info`, and `chart-1` … `chart-5`.

### Theming

`ThemeProvider` supports `light`, `dark` and `system`, persists the choice to
`localStorage`, and tracks OS changes live. A small inline script in
`index.html` applies the resolved theme before first paint to avoid a flash of
the wrong palette — if you change the storage key, change it in both places.

### Accessibility

- `Field` generates ids and wires `htmlFor`, `aria-describedby` and `aria-invalid`.
- Sortable table headers are real buttons and expose `aria-sort`.
- `Dialog` traps focus, restores it on close, and locks background scroll.
- Toasts render in an `aria-live="polite"` region.
- A global `:focus-visible` ring is defined in `index.css`; do not remove outlines locally.
- All animation is disabled under `prefers-reduced-motion`.

### Performance

Both pages are `React.lazy`-loaded, and React, Recharts, Framer Motion and
TanStack Table are split into separate vendor chunks so app-code deploys do not
invalidate cached vendor bundles.
