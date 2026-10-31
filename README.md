# Compliance Sentinel - Security Posture & Compliance Overview

A high-fidelity implementation of the **Compliance Sentinel Enterprise v4.0** UI dashboard built with React 19, Vite, and Tailwind CSS.

## Features
- **Header & Navigation**: Enterprise workspace switcher, multi-agent health status, search bar, alert center, user profile, and sidebar navigation.
- **Top KPI Cards**: Total Audits, Completed Audits with pass rates, Critical Findings with CISO action callout, High-Risk Findings with active task trackers, and Documents Analyzed with vector digest.
- **Risk Distribution by Framework**: Multi-segmented progress bars for SOC 2 Type II, ISO/IEC 27001, HIPAA, PCI-DSS v4.0, and NIST CSF 2.0 with aggregated score.
- **Agent Velocity & Cadence**: Real-time spline throughput chart (Weekly cycles, 284/day average) and 2x2 grid for Legal Analyst, Adversarial Tester, Defence Auditor, and Adjudicator.
- **Findings by Category**: Visual horizontal distribution of critical surface exposure across Identity & Access, Encryption, Logging, SLA, and TPRM with auto-remediation playbooks banner.
- **Posture Status Breakdown**: Interactive Donut chart displaying 76% Verified Controls, 11% Remediated, 8% Open Discrepancies, and 5% Unresolved Questions.
- **Recent Audits & Automated Assessments**: Live telemetry table with real-time text search, framework filtering, severity filtering, status badges, risk score tags, and pagination.
- **Interactive Modals**:
  - **New Audit Modal**: Trigger new automated runs across target VPCs and frameworks.
  - **Audit Details Modal**: Full multi-agent consensus report, exploit traces, and one-click auto-remediation playbook.
  - **Executive Briefing Modal**: Board & CISO-ready briefing with print and PDF export actions.
  - **Agent Debugger Console**: Live token throughput, agent latency, and WebSocket status.

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Server runs locally at: `http://localhost:3000`
