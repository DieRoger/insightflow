# InsightFlow — Frontend Specification

Version 1.0 · Status: **Frozen** · Target: React Developers + AI Coding Assistants

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Global Layout](#2-global-layout)
3. [Component Hierarchy](#3-component-hierarchy)
4. [Page: Dashboard](#4-page-dashboard)
5. [Page: Customer 360](#5-page-customer-360)
6. [Page: Analytics](#6-page-analytics)
7. [Page: Churn Analysis](#7-page-churn-analysis)
8. [Page: AI Copilot](#8-page-ai-copilot)
9. [Page: Reports](#9-page-reports)
10. [Page: Settings](#10-page-settings)
11. [Shared Components](#11-shared-components)
12. [State Management](#12-state-management)
13. [Loading / Error / Empty States](#13-loading--error--empty-states)
14. [Responsive Breakpoints](#14-responsive-breakpoints)
15. [Accessibility](#15-accessibility)

---

# 1. Design Principles

| # | Principle | Enforcement |
|---|-----------|-------------|
| P1 | **Every page renders data, never computes it.** | Charts and cards receive pre-computed values from API |
| P2 | **Every async component handles four states.** | Loading (skeleton), Error (message+retry), Empty (guidance), Success (data) |
| P3 | **One chart, one API endpoint.** | No chart aggregates data from multiple API responses client-side |
| P4 | **AI outputs always show evidence.** | Every AI-generated finding card includes confidence badge + evidence count |
| P5 | **Component reuse over duplication.** | Same MetricCard used on Dashboard, Analytics, Customer 360 |
| P6 | **Mobile-responsive but desktop-first.** | Dashboard prioritizes desktop; tablet usable; mobile for alerts only |

---

# 2. Global Layout

## 2.1 Shell Structure

```
┌──────────────────────────────────────────────────────────┐
│  Header                                                   │
│  [Logo] [Breadcrumb]              [🔔] [👤 User] [⚙️]    │
├──────────┬───────────────────────────────────────────────┤
│          │                                                │
│  Sidebar │  Content Area                                  │
│          │                                                │
│  📊 Dash │  ┌─────────────────────────────────────────┐  │
│  👤 Cust │  │                                         │  │
│  📈 Anal │  │    Page Content                          │  │
│  ⚠️ Churn│  │                                         │  │
│  🤖 Copl │  │                                         │  │
│  📄 Rep  │  └─────────────────────────────────────────┘  │
│  ⚙️ Sett │                                                │
│          │                                                │
├──────────┴───────────────────────────────────────────────┤
│  Status Bar (optional)                                    │
└──────────────────────────────────────────────────────────┘
```

## 2.2 Sidebar Navigation

```typescript
const NAV_ITEMS = [
    { label: "Dashboard",       icon: LayoutDashboard,  href: "/overview" },
    { label: "Customer 360",    icon: Users,             href: "/customers" },
    { label: "Analytics",       icon: BarChart3,         href: "/analytics" },
    { label: "Churn Analysis",  icon: AlertTriangle,     href: "/churn" },
    { label: "AI Copilot",      icon: Bot,               href: "/copilot" },
    { label: "Reports",         icon: FileText,          href: "/reports" },
    { label: "Settings",        icon: Settings,          href: "/settings" },
];
```

### Sidebar Behavior

| State | Behavior |
|-------|----------|
| Default | Expanded, icons + labels visible |
| Collapsed | Icon only, label on hover tooltip |
| Active route | Highlighted with accent color + left border |
| Mobile | Hidden behind hamburger menu |

## 2.3 Header

| Element | Description |
|---------|-------------|
| Logo | "InsightFlow" — links to `/overview` |
| Breadcrumb | Auto-generated from route: `Dashboard > Churn Analysis` |
| Notifications | Bell icon with badge count (anomalies + completed tasks) |
| User Menu | Avatar + dropdown: Profile, Settings, Sign Out |

---

# 3. Component Hierarchy

```
Page
 ├── Section                   ← Logical grouping (e.g., "Revenue Overview")
 │    ├── Card                 ← Container with title, optional action
 │    │    ├── MetricCard      ← Single KPI value + trend indicator
 │    │    ├── ChartCard       ← Chart with title
 │    │    ├── InsightCard     ← AI-generated finding + evidence
 │    │    └── TableCard       ← Data table with filters
 │    └── ...
 └── ...
```

### Rules

- A **Page** contains 2–5 **Sections**
- A **Section** contains 1–6 **Cards**
- A **Card** contains exactly one type of content (metric, chart, insight, or table)
- Cards in the same row auto-distribute via CSS Grid

---

# 4. Page: Dashboard

### Route

`/overview`

### Purpose

Executive-level snapshot of business health. First screen after login.

### API Calls

| Call | Endpoint | Refresh |
|------|----------|---------|
| KPIs | `GET /analytics/kpi?time_range=last_30d` | 60s |
| Trends | `GET /analytics/trend?metrics=arpu,churn_rate,mrr,active_customers&time_range=last_12m` | 5min |
| Anomalies | `GET /analytics/anomaly` | 60s |
| Risk Distribution | `GET /churn/overview` | 5min |

### Component Tree

```
DashboardPage
├── Section: "Key Metrics"
│   ├── MetricCard: ARPU          ← GET /analytics/kpi (metric=arpu)
│   ├── MetricCard: MRR           ← GET /analytics/kpi (metric=mrr)
│   ├── MetricCard: Churn Rate    ← GET /analytics/kpi (metric=churn_rate)
│   └── MetricCard: Active Users  ← GET /analytics/kpi (metric=active_customers)
│
├── Section: "Trends"
│   └── ChartCard: Multi-line trend chart
│       ← GET /analytics/trend?metrics=arpu,churn_rate,mrr
│       Chart: ECharts Line, 3 series
│       X: month, Y: value (dual Y-axis: revenue vs rate)
│
├── Section: "Risk & Alerts"       ← 2-column grid
│   ├── ChartCard: Risk Distribution (donut)
│   │   ← GET /churn/overview → risk_distribution
│   │   Chart: ECharts Pie (donut variant)
│   │   Segments: HIGH (red), MEDIUM (amber), LOW (green)
│   │
│   └── Card: Anomaly Alerts
│       ← GET /analytics/anomaly
│       List of: [severity badge] [metric] [deviation] [detected_at]
│       Max 5 items, "View All →" link to Analytics
│
└── Section: "AI Insights"
    └── InsightCard (×2–3)
        ← Cached from most recent Copilot query or auto-generated weekly insight
        Shows: title, confidence badge, key finding excerpt, evidence count
        "Ask Copilot →" action button
```

### MetricCard Specification

```
┌─────────────────────┐
│ ARPU                │
│                     │
│ $72.15              │  ← Large number (format: locale string)
│ ▲ 4.7% vs last month│  ← Trend indicator (▲ up green, ▼ down red)
│                     │
│ [Mini sparkline]    │  ← Optional 7-day trend (ECharts sparkline)
└─────────────────────┘
```

**States**:

| State | Display |
|-------|---------|
| Loading | Skeleton: gray block 200×120px, pulse animation |
| Error | "Failed to load" + Retry button |
| Empty | `—` (dash) for value, no trend |
| Success | Full MetricCard as above |

### Interaction

| Trigger | Action |
|---------|--------|
| Click MetricCard | Navigate to Analytics page, filtered to that metric |
| Click anomaly item | Navigate to Analytics > Anomaly detail |
| Click "Ask Copilot" | Navigate to Copilot page with pre-filled question |

---

# 5. Page: Customer 360

### Route

`/customers`

### Sub-Routes

| Route | Purpose |
|-------|---------|
| `/customers` | Customer list with search/filter |
| `/customers/[id]` | Individual customer 360 view |
| `/customers/[id]/usage` | Usage history detail |
| `/customers/[id]/billing` | Billing history detail |

### 5.1 Customer List (`/customers`)

**API Calls**:

| Call | Endpoint |
|------|----------|
| List | `GET /customers?status=&segment=&risk_level=&search=&page=&page_size=` |
| Segments (for filter) | `GET /analytics/segmentation?metric=customer_count&dimension=segment` |

**Component Tree**:

```
CustomerListPage
├── Section: "Filters"
│   ├── SearchInput          ← Debounced, min 2 chars
│   ├── FilterDropdown       ← Status (active/churned/suspended)
│   ├── FilterDropdown       ← Segment (premium/heavy_user/...)
│   ├── FilterDropdown       ← Risk Level (LOW/MEDIUM/HIGH)
│   └── Button: "Reset"
│
├── Section: "Summary Stats"
│   ├── StatBadge: Total Customers
│   ├── StatBadge: Active
│   ├── StatBadge: At Risk
│   └── StatBadge: Churned (last 30d)
│
└── Section: "Results"
    └── DataTable
        ← GET /customers
        Columns:
          Customer ID  |  Status  |  Lifecycle  |  Segment  |  Risk  |  ARPU  |  Tenure  |  Region
        Sortable: risk_score, arpu, tenure_days
        Click row → navigate to /customers/[id]
        Pagination: page_size=20, controls at bottom
```

**DataTable States**:

| State | Display |
|-------|---------|
| Loading | Skeleton rows (5 rows × column count), shimmer |
| Empty (no results) | Illustration + "No customers match your filters" + "Clear Filters" button |
| Empty (no data at all) | Illustration + "No customer data imported yet" + "Import Data →" link |
| Error | Error banner at top of table + Retry button |

### 5.2 Customer Detail (`/customers/[id]`)

**API Calls**:

| Call | Endpoint |
|------|----------|
| Profile | `GET /customers/{id}` |

**Component Tree**:

```
CustomerDetailPage
├── Header: Customer ID + Status Badge + Lifecycle Badge + "Back" button
│
├── Section: "Profile"                    ← 2-column grid
│   ├── Card: Personal Info
│   │   Fields: Gender, Age, City, Region, Join Date, Tenure, Contract Type
│   │
│   └── Card: Current Package
│       Fields: Package Name, Type, Monthly Price, Data Quota
│
├── Section: "Health Overview"            ← 4-column grid
│   ├── MetricCard: Churn Risk Score      ← color-coded (green <0.3, amber 0.3–0.6, red >0.6)
│   ├── MetricCard: ARPU
│   ├── MetricCard: CSAT Score
│   └── MetricCard: Days Since Last Complaint
│
├── Section: "Usage & Billing"            ← 2-column grid
│   ├── ChartCard: Usage Trend (90-day)
│   │   ← embedded in Customer360 response → usage.series
│   │   Chart: ECharts Line, data_usage_mb + voice_minutes (dual Y-axis)
│   │   "View Details →" links to /customers/[id]/usage
│   │
│   └── ChartCard: Billing History (12-month)
│       ← embedded in Customer360 response → billing.monthly_bills
│       Chart: ECharts Bar, monthly net_revenue
│       Color: green=paid, red=overdue, amber=pending
│       "View Details →" links to /customers/[id]/billing
│
├── Section: "Network & Service"          ← 2-column grid
│   ├── Card: Network Quality
│   │   Fields: Latency, Drop Rate, Coverage Score (with color indicators)
│   │
│   └── Card: Service History
│       Fields: Complaints (90d), Avg Resolution Time, CSAT
│
├── Section: "Churn Prediction"
│   └── Card: Risk Breakdown
│       ← embedded in Customer360 response → prediction
│       Top risk factors as horizontal bar chart
│       Factors: [feature name] [contribution bar] [feature value]
│       Color: red=positive contribution, blue=negative contribution
│       "View Full SHAP →" expandable panel
│
├── Section: "Recommendations"
│   └── Card: Recommended Actions (list)
│       ← embedded in Customer360 response → recommendations
│       Each item: [action text] [expected lift] [confidence badge]
│
└── Section: "Timeline"
    └── Card: Customer Journey
        ← embedded in Customer360 response → timeline
        Vertical timeline component
        Each event: [date] [icon by type] [description]
        Icons: 📅 registration, 📦 package change, 🎫 ticket, 📢 campaign
```

**States**:

| State | Display |
|-------|---------|
| Loading | Full-page skeleton with section placeholders |
| Error | Error banner + "Go Back" button |
| Not Found (404) | "Customer not found" illustration + "Back to Customers" link |
| Success | Full Customer 360 as above |
| Partial (some sections failed) | Successful sections render; failed sections show inline error + retry |

---

# 6. Page: Analytics

### Route

`/analytics`

### Purpose

Deep-dive KPI exploration with multidimensional filtering.

### Sub-Views (Tab-based or query-param)

| Tab | Purpose | API |
|-----|---------|-----|
| Overview | Multi-KPI trend comparison | `GET /analytics/trend` |
| Segmentation | KPI by dimension | `GET /analytics/segmentation` |
| Funnel | Customer lifecycle funnel | `GET /analytics/funnel` |
| Cohort | Retention cohort analysis | `GET /analytics/cohort` |
| Anomalies | Active anomaly list | `GET /analytics/anomaly` |

### Global Filters (persistent across tabs)

```
[Time Range ▼]  [Region ▼]  [Package ▼]  [Segment ▼]  [Apply]
```

### 6.1 Overview Tab

```
AnalyticsOverviewTab
├── FilterBar (shared)
│
├── Section: "Metric Selector"
│   └── MultiSelect chips: ARPU, MRR, Churn Rate, Active Customers, ...
│       ← GET /analytics/kpi (for available metric list)
│       Max 4 metrics selected at once
│
├── Section: "Trend Chart"
│   └── ChartCard: Multi-metric trend
│       ← GET /analytics/trend?metrics={selected}&time_range={filter}
│       Chart: ECharts Line, one series per metric
│       Dual Y-axis: revenue metrics (left), rate metrics (right)
│
└── Section: "Metric Detail Cards"
    └── Grid of MetricCards (one per selected metric)
        ← GET /analytics/kpi/{metric}?time_range=
        Shows: current value, previous value, change %, mini sparkline
```

### 6.2 Segmentation Tab

```
AnalyticsSegmentationTab
├── FilterBar (shared)
│
├── Controls:
│   ├── MetricSelector: [ARPU ▼]
│   ├── DimensionSelector: [Region ▼]
│   └── ChartTypeToggle: [Bar] [Treemap]
│
├── Section: "Distribution"
│   └── ChartCard
│       ← GET /analytics/segmentation?metric=&dimension=
│       Chart: ECharts Bar (horizontal) or Treemap
│       Bars: [region name] [value] [count]
│       Sorted descending by value
│
└── Section: "Detail Table"
    └── TableCard
        Same data as chart, tabular format
        Columns: Dimension | Value | Count | % of Total
```

### 6.3 Funnel Tab

```
AnalyticsFunnelTab
└── Section: "Customer Lifecycle Funnel"
    └── ChartCard
        ← GET /analytics/funnel
        Chart: ECharts Funnel
        Stages: Visitor → Subscriber → Active → Premium → Retained
        Each stage: [name] [count] [% of previous] [% of total]
        Color gradient: dark (top) to light (bottom)
```

### 6.4 Cohort Tab

```
AnalyticsCohortTab
├── Controls:
│   └── MetricToggle: [Retention] [Revenue]
│
└── Section: "Cohort Retention Matrix"
    └── ChartCard
        ← GET /analytics/cohort?metric=
        Chart: ECharts Heatmap
        Rows: cohort (acquisition month)
        Columns: month number (0, 1, 3, 6, 12)
        Cell color: white (0%) → dark blue (100%)
        Cell label: retention rate %
        Click cell → show cohort size + absolute retained count
```

### 6.5 Anomalies Tab

```
AnalyticsAnomaliesTab
└── Section: "Active Anomalies"
    └── TableCard
        ← GET /analytics/anomaly
        Columns:
          Severity | Metric | Region | Observed | Expected | Deviation % | Detected At
        Sortable: severity, deviation_pct
        Row color: red (HIGH), amber (MEDIUM), none (LOW)
        Click row → navigate to relevant metric trend with anomaly highlighted
```

---

# 7. Page: Churn Analysis

### Route

`/churn`

### Purpose

Churn-focused analytics: overview dashboard, risk exploration, prediction interface.

### Sub-Views

| Tab | Purpose |
|-----|---------|
| Overview | Churn rate, trends, risk distribution |
| High-Risk Customers | Filterable list of high-risk customers |
| Prediction | Single-customer prediction interface |

### 7.1 Overview Tab

```
ChurnOverviewTab
├── Section: "Key Churn Metrics"
│   ├── MetricCard: Current Churn Rate  ← GET /churn/overview
│   ├── MetricCard: Churn Trend (MoM)
│   ├── MetricCard: High-Risk Customers (count)
│   └── MetricCard: Avg Churn Probability
│
├── Section: "Churn Trend"               ← 2-column grid
│   ├── ChartCard: Churn rate over time
│   │   Chart: ECharts Line, churn_rate by month
│   │   Overlay: previous year comparison (dashed line)
│   │
│   └── ChartCard: Risk Distribution
│       Chart: ECharts Donut, HIGH/MEDIUM/LOW
│
├── Section: "Top Risk Factors"
│   └── ChartCard: Feature importance
│       ← GET /churn/overview → top_risk_factors
│       Chart: ECharts Horizontal Bar
│       [factor name] [importance bar] [importance value]
│
└── Section: "Churn by Segment"
    └── ChartCard: Churn rate × dimension
        ← GET /churn/overview → churn_by_region + churn_by_segment
        Chart: ECharts Grouped Bar
        X: region (or segment), Y: churn_rate
```

### 7.2 High-Risk Customers Tab

```
ChurnHighRiskTab
├── FilterBar
│   ├── RiskLevelDropdown: [HIGH] [MEDIUM] [LOW] [ALL]
│   ├── RegionDropdown
│   └── SegmentDropdown
│
├── Section: "Summary"
│   ├── StatBadge: Total High-Risk
│   ├── StatBadge: Avg Risk Score
│   └── StatBadge: Potential Revenue at Risk
│
└── Section: "Customer Table"
    └── DataTable
        ← GET /customers?risk_level=HIGH&page=&page_size=
        Columns:
          Customer ID | Risk Score | Risk Level | Top Factor | ARPU | Region | Segment
        Sortable: risk_score, arpu
        Click row → /customers/[id]
        Bulk action (future): "Add to Retention Campaign"
```

### 7.3 Prediction Tab

```
ChurnPredictionTab
├── Section: "Predict Churn"
│   └── Card
│       ├── Input: Customer ID text field + "Predict" button
│       │
│       ├── (After prediction) Result Panel:
│       │   ├── Big number: Risk Score (color-coded)
│       │   ├── Badge: Risk Level (LOW/MEDIUM/HIGH)
│       │   ├── Confidence: "Model confidence: 93%"
│       │   │
│       │   ├── Sub-section: "Top Risk Factors"
│       │   │   └── Horizontal bar chart (SHAP contributions)
│       │   │       Red bar = increases risk, Blue bar = decreases risk
│       │   │       Each bar: [feature] [value] [contribution]
│       │   │
│       │   └── Sub-section: "Recommendations"
│       │       └── List of recommended actions with expected impact
│       │
│       └── Link: "View Full Customer Profile →"
│
└── Section: "Batch Prediction"
    └── Card
        ├── Text: "Last batch: 2026-08-01 02:00 | 950,000 predictions | 45,000 high-risk"
        ├── Button: "Run Batch Prediction"
        │   ← POST /churn/predict/batch → task_id
        │   Shows progress bar (poll GET /system/tasks/{task_id})
        └── Status: idle → "Running... 45%" → "Completed ✓"
```

**Prediction States**:

| State | Display |
|-------|---------|
| Idle | Input field + Predict button |
| Loading | Button shows spinner, "Analyzing customer data..." |
| Error | "Prediction failed: {message}" + Retry |
| Not Found | "Customer ID not found" |
| Already Churned | "Customer has already churned — prediction not applicable" |
| Success | Full result panel as above |

---

# 8. Page: AI Copilot

### Route

`/copilot`

### Purpose

Natural language interface for business questions. The most complex page in terms of interaction design.

### Layout

```
┌──────────────────────────────────────────────────────────┐
│  AI Copilot                                              │
├────────────────────────────┬─────────────────────────────┤
│                            │                              │
│  Conversation Panel (60%)  │  Evidence Panel (40%)        │
│                            │                              │
│  ┌──────────────────────┐  │  ┌───────────────────────┐  │
│  │ User: Why did churn  │  │  │ 📊 Evidence           │  │
│  │ increase in East?    │  │  │                       │  │
│  └──────────────────────┘  │  │ Source: fact_service  │  │
│                            │  │ Metric: complaint_freq│  │
│  ┌──────────────────────┐  │  │ Sample: 45,210        │  │
│  │ 🤖 Copilot:          │  │  │ Confidence: 95%       │  │
│  │                      │  │  │                       │  │
│  │ Premium churn +23%   │  │  │ [View SQL]            │  │
│  │ [confidence: 92%]    │  │  └───────────────────────┘  │
│  │                      │  │                              │
│  │ Evidence: 2 sources  │  │  ┌───────────────────────┐  │
│  │                      │  │  │ 📊 Evidence           │  │
│  │ Recommendation:      │  │  │ Source: fact_network  │  │
│  │ Network optimization  │  │  │ ...                   │  │
│  │ [confidence: 87%]    │  │  └───────────────────────┘  │
│  │                      │  │                              │
│  │ [Generate Report]    │  │                              │
│  └──────────────────────┘  │                              │
│                            │                              │
│  ┌──────────────────────┐  │                              │
│  │ Ask a question...   ▶│  │                              │
│  └──────────────────────┘  │                              │
│                            │                              │
└────────────────────────────┴──────────────────────────────┘
```

### API Calls

| Call | Endpoint |
|------|----------|
| Chat | `POST /copilot/chat` |
| History | `GET /copilot/history` |
| Workflow Trace | `GET /copilot/workflows/{id}` |

### Component Tree

```
CopilotPage
├── ConversationPanel (left, 60%)
│   ├── MessageList
│   │   ├── UserMessage (right-aligned bubble)
│   │   │   └── Text content
│   │   │
│   │   └── CopilotMessage (left-aligned, structured)
│   │       ├── WorkflowProgressBar (during execution)
│   │       │   └── Animated steps: Planner → SQL → Analytics → Evidence → Decision → Writer → Review
│   │       │       Current step: spinner, Completed: ✓, Failed: ✗
│   │       │
│   │       ├── Content (after completion):
│   │       │   ├── Intent badge: "Churn Root Cause Analysis"
│   │       │   ├── Findings list
│   │       │   │   └── FindingCard:
│   │       │   │       ├── Title
│   │       │   │       ├── ConfidenceBadge (color-coded)
│   │       │   │       ├── EvidenceSummary: "2 evidence sources"
│   │       │   │       └── Expandable: full evidence detail
│   │       │   │
│   │       │   ├── Decisions list
│   │       │   │   └── DecisionCard:
│   │       │   │       ├── Recommendation text
│   │       │   │       ├── Business Impact
│   │       │   │       ├── Expected Outcome
│   │       │   │       └── ConfidenceBadge
│   │       │   │
│   │       │   └── Actions:
│   │       │       ├── "Generate Report" button
│   │       │       └── "View SQL" expandable code block
│   │       │
│   │       └── ReviewOverrideWarning (if review_override=true)
│   │           └── Amber banner: "⚠️ This analysis was auto-published after 3 review attempts. Confidence may be lower than indicated."
│   │
│   └── InputArea (sticky bottom)
│       ├── TextArea: "Ask a business question..."
│       ├── CharCounter: 0/500
│       ├── ContextChips (optional):
│       │   └── [Region ▼] [Time Range ▼]
│       └── SendButton (disabled when empty or loading)
│
├── EvidencePanel (right, 40%)
│   ├── Header: "Evidence ({count})"
│   └── EvidenceList
│       └── EvidenceCard (×N):
│           ├── Source Table badge
│           ├── Metric name
│           ├── Description
│           ├── Sample Size
│           ├── Confidence
│           └── Expandable: Generated SQL (syntax-highlighted code block)
│
└── (Optional) DebugPanel
    └── Collapsible: Workflow trace → GET /copilot/workflows/{id}
```

### Interaction Flow

```
User types question → Press Enter / Click Send
    │
    ▼
Input disabled, Send button = spinner
    │
    ▼
WorkflowProgressBar appears
    │
    ├── Agent steps animate: Planner → SQL → Analytics → Evidence → Decision → Writer → Review
    │   (Real-time via WebSocket /ws/copilot/{workflow_id} if available, else polling)
    │
    ▼
CopilotMessage renders with structured content
    │
    ▼
EvidencePanel populates from response.evidence[]
    │
    ▼
User can:
    ├── Click evidence card → scroll to detail / copy SQL
    ├── Click "Generate Report" → POST /reports/generate (async)
    ├── Click "View Full Customer" → navigate to /customers/[id]
    └── Ask follow-up question (context is NOT preserved — each question is independent in MVP)
```

### States

| State | Display |
|-------|---------|
| Empty (no history) | Welcome message: "Ask me anything about your telecom operations" + 3 example questions as suggestion chips |
| Loading (workflow running) | WorkflowProgressBar with animated agent steps |
| Partial (some agents failed) | Yellow warning + partial results + "Reviewer override" flag |
| Error (workflow failed) | Red error card + "The AI workflow could not complete: {reason}" + "Try rephrasing your question" |
| Success | Full CopilotMessage + EvidencePanel |
| Streaming (future) | Text appears token-by-token via WebSocket |

### Suggestion Chips (Empty State)

```typescript
const SUGGESTIONS = [
    "Why did churn increase this month?",
    "Which customers are most likely to churn?",
    "Show me ARPU trends by region",
    "What's driving revenue decline in the West region?",
    "Generate a weekly executive summary",
];
```

---

# 9. Page: Reports

### Route

`/reports`

### Purpose

Browse, generate, and download business reports.

### Component Tree

```
ReportsPage
├── Section: "Generate Report"
│   └── Card
│       ├── TypeSelector: [Daily] [Weekly] [Monthly] [Quarterly] [Executive]
│       ├── FormatSelector: [Markdown] [PDF]
│       ├── (Optional) Region multi-select
│       ├── (Optional) Based on Copilot workflow dropdown
│       └── Button: "Generate Report"
│           ← POST /reports/generate → task_id
│           Shows progress bar
│
└── Section: "Past Reports"
    └── DataTable
        ← GET /reports?type=&page=&page_size=
        Columns:
          Title | Type | Format | Status | Generated At | Size | Download
        Sortable: generated_at
        Status badges: Published (green), Generating (amber spinner), Failed (red)
        Actions: Download (cloud icon), View (eye icon)
```

### Report Generation Flow

```
Click "Generate Report"
    │
    ▼
Button disabled, shows "Generating..."
    │
    ▼
POST /reports/generate → 202 { task_id }
    │
    ▼
Progress bar (poll GET /system/tasks/{task_id} every 2s)
    │
    ├── Running: "Generating report... 60%"
    │
    ▼
Completed → Report appears in table (auto-refresh)
    │
    ▼
Click Download → GET /reports/{id}/download (file download)
```

---

# 10. Page: Settings

### Route

`/settings`

### Purpose

User preferences, system status. Minimal for MVP.

### Component Tree

```
SettingsPage
├── Section: "User Preferences"
│   └── Card
│       ├── ThemeToggle: [Light] [Dark] [System]
│       ├── DefaultTimeRange: [Last 7 days ▼] [Last 30 days] [Last 90 days]
│       └── NotificationToggle: [On] [Off]
│
└── Section: "System Status"
    └── Card
        ← GET /system/health
        ├── Version: "1.0.0"
        ├── Uptime: "4 days 2 hours"
        ├── DB Status: ● Online
        ├── Redis Status: ● Online
        ├── Storage Status: ● Online
        └── LLM Provider: ● Online (gpt-4o)
```

---

# 11. Shared Components

These components are used across multiple pages and must be implemented once.

## 11.1 MetricCard

```typescript
interface MetricCardProps {
    title: string;
    value: number | string;
    format?: "currency" | "percentage" | "number" | "duration";
    trend?: {
        direction: "up" | "down" | "stable";
        value: number;           // e.g., 4.7
        label: string;           // e.g., "vs last month"
    };
    sparkline?: { period: string; value: number }[];
    color?: "default" | "success" | "warning" | "danger";
    loading?: boolean;
    error?: string;
    onRetry?: () => void;
    onClick?: () => void;
}
```

## 11.2 ConfidenceBadge

```typescript
interface ConfidenceBadgeProps {
    confidence: number;          // 0.0–1.0
    showLabel?: boolean;         // default true
    size?: "sm" | "md" | "lg";
}

// Color mapping:
// ≥ 0.85 → green ("High confidence")
// 0.70–0.85 → amber ("Medium confidence")
// 0.60–0.70 → orange ("Low confidence")
// < 0.60 → red ("Uncertain — review required")
```

## 11.3 EvidenceCard

```typescript
interface EvidenceCardProps {
    sourceTable: string;
    metric: string;
    description: string;
    sampleSize?: number;
    confidence: number;
    sql?: string;                // Expandable code block
}
```

## 11.4 InsightCard

```typescript
interface InsightCardProps {
    title: string;
    confidence: number;
    evidenceCount: number;
    summary: string;             // 1–2 line excerpt
    onClick?: () => void;        // Navigate to full detail
}
```

## 11.5 WorkflowProgressBar

```typescript
interface WorkflowProgressBarProps {
    agents: {
        name: string;            // "Planner", "SQL Agent", etc.
        status: "pending" | "running" | "completed" | "failed";
    }[];
    currentAgent?: string;
}
```

## 11.6 DataTable

```typescript
interface DataTableProps<T> {
    columns: ColumnDef<T>[];
    data: T[];
    loading?: boolean;
    error?: string;
    emptyMessage?: string;
    pagination?: {
        page: number;
        pageSize: number;
        total: number;
        onPageChange: (page: number) => void;
    };
    sorting?: {
        column: string;
        direction: "asc" | "desc";
        onSort: (column: string, direction: "asc" | "desc") => void;
    };
    onRowClick?: (row: T) => void;
}
```

---

# 12. State Management

### Strategy

| State Type | Tool | Reason |
|------------|------|--------|
| **Server data** (customers, KPIs, reports) | TanStack Query | Caching, refetch, deduplication |
| **UI state** (sidebar open, theme, active tab) | Zustand | Lightweight, no boilerplate |
| **Form state** (search, filters) | React Hook Form + Zod | Validation |
| **URL state** (page, filters, selected tab) | next/navigation searchParams | Shareable, bookmarkable |
| **Real-time** (Copilot progress) | WebSocket → Zustand | Push updates |

### Zustand Store (UI State Only)

```typescript
// stores/ui.ts
interface UIState {
    sidebarOpen: boolean;
    theme: "light" | "dark" | "system";
    toggleSidebar: () => void;
    setTheme: (theme: "light" | "dark" | "system") => void;
}
```

### TanStack Query Keys

```typescript
// Organized by domain
export const queryKeys = {
    analytics: {
        kpis: (filters: KPIFilters) => ["analytics", "kpis", filters] as const,
        trend: (params: TrendParams) => ["analytics", "trend", params] as const,
        anomalies: () => ["analytics", "anomalies"] as const,
        segmentation: (params: SegmentParams) => ["analytics", "segmentation", params] as const,
    },
    customers: {
        list: (filters: CustomerFilters) => ["customers", "list", filters] as const,
        detail: (id: string) => ["customers", "detail", id] as const,
    },
    churn: {
        overview: () => ["churn", "overview"] as const,
        prediction: (id: string) => ["churn", "prediction", id] as const,
    },
    copilot: {
        history: (page: number) => ["copilot", "history", page] as const,
        workflow: (id: string) => ["copilot", "workflow", id] as const,
    },
    reports: {
        list: (filters: ReportFilters) => ["reports", "list", filters] as const,
    },
};
```

---

# 13. Loading / Error / Empty States

### Rule (AR-073)

> Every asynchronous component MUST handle four states: loading, error, empty, success.

### Standard Implementations

**Loading**:
```tsx
// Skeleton for cards
<Skeleton className="h-[120px] w-full rounded-lg" />

// Skeleton for tables
<TableSkeleton rows={5} columns={columns.length} />

// Skeleton for charts
<Skeleton className="h-[300px] w-full rounded-lg" />
```

**Error**:
```tsx
<ErrorState
    title="Failed to load data"
    message={error.message}
    requestId={error.request_id}     // For debugging
    onRetry={() => refetch()}
/>
```

**Empty (no data)**:
```tsx
<EmptyState
    icon={<DatabaseIcon />}
    title="No data yet"
    description="Import your first dataset to see analytics."
    action={{ label: "Import Data", href: "/settings/import" }}
/>
```

**Empty (no results)**:
```tsx
<EmptyState
    icon={<SearchIcon />}
    title="No customers match your filters"
    action={{ label: "Clear Filters", onClick: resetFilters }}
/>
```

### Loading Sequence (Page Level)

```
1. Route change → immediate skeleton render
2. All API calls fire in parallel
3. Each section transitions independently:
   Skeleton → (Error | Empty | Success)
4. Page is "ready" when all sections resolve
```

---

# 14. Responsive Breakpoints

| Breakpoint | Width | Target |
|------------|-------|--------|
| `sm` | ≥ 640px | Mobile landscape |
| `md` | ≥ 768px | Tablet portrait |
| `lg` | ≥ 1024px | Tablet landscape / small desktop |
| `xl` | ≥ 1280px | Desktop (primary target) |
| `2xl` | ≥ 1536px | Large desktop |

### Layout Adaptations

| Element | Desktop (xl) | Tablet (md) | Mobile (sm) |
|---------|-------------|-------------|-------------|
| Sidebar | Expanded | Collapsed (icon only) | Hidden (hamburger) |
| MetricCards row | 4 columns | 2 columns | 1 column |
| Chart + Table | Side by side | Stacked | Stacked (table hidden, chart only) |
| Copilot layout | Conversation + Evidence | Conversation only (evidence in accordion) | Conversation full-width |
| DataTable | Full columns | Reduced columns (hide low-priority) | Card list instead of table |

---

# 15. Accessibility

| Requirement | Implementation |
|-------------|---------------|
| Keyboard navigation | All interactive elements focusable via Tab. Enter/Space to activate. Escape to close modals. |
| Screen readers | Semantic HTML (`<nav>`, `<main>`, `<section>`, `<article>`). `aria-label` on icon-only buttons. `role` on custom components. |
| Focus indicators | Visible focus ring on all focusable elements. `focus-visible` only (not on click). |
| Color contrast | WCAG AA minimum (4.5:1 for text, 3:1 for large text). Charts use patterns + colors. |
| Color independence | Charts distinguishable in grayscale. Risk levels use icons + color (not color alone). |
| Reduced motion | Respect `prefers-reduced-motion`. Disable chart animations, skeleton pulse. |

---

# Document Freeze

This document freezes the **frontend component architecture and interaction design** for InsightFlow Version 1.0.

From this point onward:

- Every page must follow the component tree defined here.
- Every async component must implement loading, error, empty, and success states.
- Shared components (MetricCard, ConfidenceBadge, EvidenceCard, DataTable) must be implemented once and reused.
- Charts must consume pre-computed API data — clientside KPI calculation is forbidden (AR-070).
- AI-generated outputs must always show confidence and evidence (AR-072).
- State management follows the TanStack Query (server) + Zustand (UI) + URL (shareable) pattern.
