---
goal: Implementation Plan — Phase 9: Copilot UI
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 1 (Foundation), Phase 2 (Memory Layer), Phase 4 (Detection Engine)
tags: implementation, ui, react, nextjs
---

# Phase 9: Copilot UI

## Overview

Build the React/Next.js frontend with three core views: Anomaly Dashboard, Incident RCA & Remediation Review, and Semantic Archive Search. Implements RBAC (dba_readonly / dba_admin), MFA-gated remediation approval, and API route proxying to all backend services.

**Estimated Duration:** 2 sprints (Sprints 17–18)

**Dependencies:** Phase 1 (Next.js scaffold exists), Phase 2 (memory service API ready), Phase 4 (incidents flowing)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 9.1 | Create layout + sidebar | 1 hr | `src/copilot-ui/src/app/layout.tsx`, `Sidebar.tsx` | ⬜ |
| 9.2 | Build Dashboard page | 2 hr | `src/copilot-ui/src/app/dashboard/page.tsx` | ⬜ |
| 9.3 | Build Incident Detail page | 2 hr | `src/copilot-ui/src/app/incidents/[id]/page.tsx` | ⬜ |
| 9.4 | Build Search page | 1.5 hr | `src/copilot-ui/src/app/search/page.tsx` | ⬜ |
| 9.5 | Create API route proxies | 1 hr | `src/copilot-ui/src/app/api/*/route.ts` | ⬜ |
| 9.6 | Implement NextAuth + RBAC | 1.5 hr | `src/copilot-ui/src/lib/auth.ts` | ⬜ |
| 9.7 | Component tests | 1 hr | `tests/unit/copilot-ui/` | ⬜ |
| 9.8 | Integration test: auth + API | 1 hr | `tests/integration/test_ui_auth.py` | ⬜ |

---

## Task 9.1: Layout + Sidebar

**File:** `src/copilot-ui/src/app/layout.tsx`
- Root layout with Sidebar component and main content area.
- Import globals.css with Tailwind directives.
- Metadata: title "AI DBA Copilot".

**File:** `src/copilot-ui/src/components/Sidebar.tsx`
```typescript
// Navigation items
const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: Activity },
  { href: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/settings', label: 'Settings', icon: Settings },
];
```

---

## Task 9.2: Dashboard Page

**File:** `src/copilot-ui/src/app/dashboard/page.tsx`

**Components required:**
- `StatsBar`: Shows counts total/critical/high/medium/low
- `SeverityFilter`: All | Critical | High | Medium | Low buttons
- `IncidentStream`: Auto-polling list every 10s
- `IncidentCard`: Severity badge, domain, db_target, detection count, time

**Data flow:** GET /api/incidents?status=ACTIVE → poll every 10s using `useEffect` with `setInterval`

---

## Task 9.3: Incident Detail Page

**File:** `src/copilot-ui/src/app/incidents/[id]/page.tsx`

**Components required:**
- `RCAPanel`: Renders rca_text markdown in card
- `ActionStepsList`: Ordered list with type badges (AUTO=green, APPROVAL_REQUIRED=yellow, BLOCKED=red)
- `ConfidenceBar`: Green ≥0.80, Yellow ≥0.60, Red <0.60
- `RiskBadge`: LOW(green), MEDIUM(yellow), HIGH(red)
- `ApprovalButton`: Enabled for admin, disabled with tooltip for readonly

---

## Task 9.4: Search Page

**File:** `src/copilot-ui/src/app/search/page.tsx`

- Debounced search input (300ms)
- Results list with similarity scores, source type badges, content preview
- Click-through to incident detail

---

## Task 9.5: API Route Proxies

```typescript
// src/app/api/incidents/route.ts — proxies to memory service
// src/app/api/incidents/[id]/route.ts — single incident
// src/app/api/recommendations/incident/[id]/route.ts — recommendations
// src/app/api/search/route.ts — semantic search
// src/app/api/forecast/storage/[target]/route.ts — forecasts
// src/app/api/approve/route.ts — remediation execution (admin only)
```

---

## Task 9.6: NextAuth + RBAC

**File:** `src/copilot-ui/src/lib/auth.ts`

```typescript
import NextAuth from "next-auth";
import { OIDCConfig } from "next-auth/providers";

export const authOptions = {
  providers: [
    OIDCConfig({
      clientId: process.env.OIDC_CLIENT_ID!,
      clientSecret: process.env.OIDC_CLIENT_SECRET!,
      issuer: process.env.OIDC_ISSUER!,
    }),
  ],
  callbacks: {
    async session({ session, token }) {
      session.user.role = token.role as string;
      return session;
    },
    async jwt({ token, account }) {
      if (account?.id_token) {
        const groups = JSON.parse(atob(account.id_token.split('.')[1])).groups || [];
        token.role = groups.includes('DBA-Admin') ? 'dba_admin' : 'dba_readonly';
      }
      return token;
    },
  },
};
```

---

## Task 9.7–9.8: Tests

**Component tests** (`tests/unit/copilot-ui/`):
- `IncidentCard.test.tsx`: Renders severity badge, click handler
- `RCAPanel.test.tsx`: Renders markdown
- `ConfidenceBar.test.tsx`: Correct color per threshold
- `ApprovalButton.test.tsx`: Enabled for admin, disabled for readonly

## Phase 9 Completion Criteria

- [ ] Dashboard loads incidents with 10s polling
- [ ] SeverityFilter correctly filters incident list
- [ ] Incident detail shows RCA, action steps, confidence, risk
- [ ] Approval button disabled for readonly, enabled for admin
- [ ] Search returns results with debounced input
- [ ] API routes proxy correctly without exposing backend URLs
- [ ] NextAuth redirects unauthenticated users to login
- [ ] Component tests pass
