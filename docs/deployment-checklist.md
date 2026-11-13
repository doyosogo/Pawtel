# Final manual deployment handoff

**No verified public URL exists.** Configuration and local verification do not equal
a hosted release. Follow [deployment.md](deployment.md) and the [exact environment inventory](deployment-environment.md) for the full variable table,
current pricing references, provider steps and caveats. Nothing below is automated
by PR CI and no account/resource/DNS operation should be delegated implicitly.

Follow the [numbered phases A–H](deployment-preflight.md) when executing this checklist.
That guide also covers suspension/deletion, backup implications and rollback limits.

## Before spending or deploying

- [ ] Review and commit/push changes yourself. Confirm CI green for the EXACT release
      SHA. The verified baseline is [da2255d / run 43317246922](https://github.com/doyosogo/Pawtel/actions/runs/43317246922).
- [ ] Review Render's actual price estimate and provider permissions yourself. The
      selected paid app/database path is not a free Blueprint.
- [ ] Keep automatic deployment Off. No provider write secrets belong in PR CI.

## Provision/configure yourself

- [ ] One Render Python Web Service and PostgreSQL18, both Singapore; repo root blank.
- [ ] Database and role exactly `pawtel_portfolio`, 1GB, external access disabled;
      one app instance/worker. Do not attach an existing real-user database.
- [ ] Apply `render.yaml` settings, pinned runtimes, build/pre-deploy/start scripts
      and `/ready`. Set actual HTTPS origin/hostname lists, Secure cookies,
      SERVE_FRONTEND=true and PORTFOLIO_DEMO=true. Omit TEST_DATABASE_URL.
- [ ] Keep database, Stripe secret/webhook and Cloudinary credentials only in the
      provider secret store. Only the sandbox publishable key may use VITE_.
- [ ] Deploy your reviewed release and inspect safe migration/startup/readiness logs.
- [ ] Configure a private synthetic passphrase; run `seed_portfolio` yourself as
      documented. Do not use the local-only seed or publish shared mutable credentials.
- [ ] Configure sandbox Stripe HTTPS destination/events/version/signing secret and
      return URL; configure dedicated Cloudinary media. Rebuild for public-key changes.

## Verify before publishing a link

- [ ] Run `python -m tools.deployment_smoke --frontend https://YOUR_ACTUAL_ORIGIN`
      from backend with its environment active. This is read-only; replace the placeholder.
- [ ] Personally test marketplace/search/images, Owner login/Pets/request, Host
      accept, Owner AWAITING_PAYMENT and configured Stripe test checkout/webhook state.
- [ ] Test Host draft/edit/photo/publish/archive; check direct deep-route refresh.
- [ ] Inspect logout/back navigation, registration refusal, demo notices, keyboard
      focus and mobile widths. Use only synthetic inputs.
- [ ] Check health/readiness, request IDs, cookie attributes and security headers
      once on HTML/API. Verify near-limit synthetic image upload under actual ingress limits.
- [ ] Review built-in logs, alerts/cost limits, backup/PITR limitations and rollback
      compatibility; do not blindly downgrade a payment/media database.
- [ ] Rotate private invited access. Review synthetic Booking/media maintenance;
      the seed is setup/rotation, not a destructive reset or retention scheduler.
- [ ] Only after success, update README's live URL and the GitHub website field.

## Portfolio assets and GitHub settings — manually

- [ ] Capture the six [manual screenshot states](images/README.md), review privacy,
      then add real images with alt text. No fake screenshots or provider dashboards.
- [ ] Suggested description: “Australian pet-boarding portfolio MVP: React,
      TypeScript, FastAPI, PostgreSQL, transactional bookings and Stripe sandbox payments.”
- [ ] Suggested topics: `react`, `typescript`, `fastapi`, `postgresql`, `sqlalchemy`,
      `stripe`, `playwright`, `github-actions`, `portfolio`, `pet-boarding`.
- [ ] Pin the repository if it represents your strongest work. Leave website empty
      until a real URL is verified. Social preview idea: PAWTEL wordmark, one synthetic
      marketplace capture and a small architecture cue; no credentials or fake metrics.
