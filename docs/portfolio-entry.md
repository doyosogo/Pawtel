# Portfolio-site copy

## PAWTEL — pet-boarding marketplace

A production-shaped full-stack portfolio MVP for discovering pet stays and
managing Owner/Host Booking workflows. Built with React, TypeScript, FastAPI and
PostgreSQL.

**Stack:** React, TypeScript, TanStack Query, FastAPI, SQLAlchemy, PostgreSQL,
Stripe Checkout, Cloudinary, GitHub Actions and Playwright.

- Ownership-scoped resources and cookie sessions with CSRF protection.
- PostgreSQL row locks and transactional capacity rechecks for Host acceptance.
- Server-authoritative price snapshots and signed, deduplicated payment
  webhooks.
- Recoverable media/provider failures rather than assumed distributed
  transactions.
- Real frontend/API/database tests plus a separately verified static showcase.

[Live frontend showcase](https://pawtel-ashen.vercel.app/) ·
[Source and engineering documentation](https://github.com/doyosogo/Pawtel)

The public Vercel experience uses synthetic data and simulated actions; it
creates no real accounts, Bookings or payments. The repository contains the
full-stack implementation. Its Render deployment is prepared, not live; payments
remain sandbox-only and hosted Cloudinary acceptance is manual.

## LinkedIn-ready project description

I built PAWTEL, a pet-boarding marketplace portfolio MVP with React/TypeScript,
FastAPI and PostgreSQL. I focused on private Owner/Host resources,
concurrency-safe Booking acceptance, server-owned prices, Stripe webhook
authority and recovery from media-provider failures, supported by CI and
full-stack tests. I also deployed a synthetic Vercel showcase so reviewers can
explore the shared interface without setup; it is separate from the real backend
and does not process real payments.
