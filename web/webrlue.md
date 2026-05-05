# Frontend Rules

## Tech stack
- Next.js (App Router)
- Tailwind CSS
- shadcn/ui
- Radix UI
- TanStack Table for all major tables
- Charts should use shadcn charts / Recharts first
- Do not introduce extra UI frameworks unless explicitly requested

## Product type
This project is a professional quant + news-driven market intelligence dashboard.
It is not a generic SaaS admin panel.

## Core layout
The homepage should contain only 3 main zones:
1. top status bar
2. left watchlist / symbol list
3. center main content area

## Main content priorities
The center area should prioritize:
- key charts
- event/news flow
- sentiment panels
- rankings / tables
- filters that are compact and professional

Use tables, lists, timelines, and compact status panels more than decorative cards.

## Visual style
Reference style:
- Linear
- Vercel
- Bloomberg Terminal

Visual requirements:
- restrained
- professional
- dense information layout
- grayscale-first
- single accent color
- compact spacing
- clear hierarchy
- data-first, not decoration-first

## Avoid
- generic admin dashboard style
- oversized cards
- too many colorful widgets
- heavy shadows
- large rounded corners
- excessive gradients
- too much empty space
- over-designed hero sections
- unnecessary animations
- mixing multiple visual styles on one page

## Chart rules
- Charts should be meaningful, not decorative
- Prefer a small number of high-value charts
- Avoid BI-dashboard overload
- Prioritize time series, comparisons, rankings, and event-linked views
- Keep chart styling restrained and consistent

## Table rules
- Tables are first-class UI, not secondary
- Use TanStack Table for flexible professional data tables
- Dense but readable
- Sorting, filtering, pinning, and compact row layout are preferred
- Do not make tables look like toy SaaS widgets

## Interaction rules
- Keep interactions simple and professional
- Use hover, tabs, filters, and drawers only when needed
- Prefer stable layouts over excessive popovers and motion
- Optimize for research workflow, not marketing presentation

## Implementation rules
Before building a page:
1. define page structure
2. define component hierarchy
3. define data blocks
4. then implement UI

Do not jump directly into fully styled pages without first deciding layout and hierarchy.

## Default homepage modules
Homepage should usually include:
- top market/status bar
- left symbol watchlist
- center key chart section
- center event/news timeline
- center sentiment summary
- center ranking/table section

## Design goal
The final result should feel like a serious research workstation:
- trustworthy
- efficient
- information-dense
- visually controlled
- good enough without over-design