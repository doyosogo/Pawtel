# Résumé material

Choose two or three bullets for the role; do not combine every group. These
describe Victor's portfolio work, not customer scale, revenue or unmeasured
performance gains. Current counts and the verified CI baseline live in the
[README](../README.md).

## Junior Software Engineer

- Built an Australian pet-boarding portfolio MVP with React/TypeScript, FastAPI
  and PostgreSQL, covering discovery, Pet Profiles and Owner/Host Booking
  workflows.
- Tested component, API/database and headless user journeys in GitHub Actions;
  reproduced CI environment and browser-cache failures without weakening
  safeguards.

## Full-stack Developer

- Implemented the React-to-FastAPI Booking journey with private resources,
  CSRF-aware sessions, query invalidation and server-owned AUD price snapshots.
- Integrated Stripe Checkout/webhook confirmation and Cloudinary Listing media,
  with explicit reconciliation and cleanup for provider/database partial
  failures.
- Deployed a synthetic Vercel showcase using shared UI and a local data adapter;
  kept the real backend integration and full-stack deployment path separate.

## Backend Developer

- Designed transactional Booking acceptance using PostgreSQL Listing-first row
  locks and capacity rechecks; tested competing acceptors with separate
  connections.
- Implemented opaque session authentication, Argon2id password hashing, CSRF and
  ownership-scoped queries for private Pet, Listing and Booking resources.
- Persisted payment attempts and deduplicated signed Stripe webhook events,
  handling uncertain outcomes and late payments without reviving cancelled
  stays.

## Frontend Developer

- Built responsive marketplace, Pet, Booking and Host views using React Router,
  TypeScript and TanStack Query, with accessible forms and mutation-driven
  refresh.
- Implemented a static showcase using the same components and synthetic
  personas; verified the public Vercel journey without backend/provider network
  traffic.
- Integrated Stripe-controlled Checkout Elements in real API mode while keeping
  client secrets transient and excluding payment controls from the showcase.

## Project description

PAWTEL is a production-shaped pet-boarding portfolio MVP built with
React/TypeScript, FastAPI and PostgreSQL. It combines private Owner/Host
workflows, concurrency-safe reservations, server-authoritative prices, Stripe
sandbox payments and Cloudinary media. A live synthetic frontend showcase
provides instant recruiter access; full-stack hosting is prepared separately and
is not live.

When copying a numerical claim, use the current verified totals in the README.
Do not describe the project as production-ready or claim users, revenue, load
capacity or percentage improvements that have not been measured.
