# Stripe billing setup (FleetFlow)

## Product model

- **$10 USD per vehicle / month** (configurable via `BILLING_UNIT_AMOUNT_CENTS`, default `1000`).
- **7-day free trial** with **payment method required** at signup (Stripe Checkout `mode: subscription` + `trial_period_days`).
- Quantity on the subscription tracks **vehicles in the company** (synced when vehicles are added or removed).

API version: **2026-04-22.dahlia** (set in `STRIPE_API_VERSION`).

## Environment variables

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
# Optional: use a Dashboard Price instead of auto-creating one
STRIPE_PRICE_ID=price_...
BILLING_TRIAL_DAYS=7
BILLING_UNIT_AMOUNT_CENTS=1000
BILLING_CURRENCY=usd
BILLING_ENFORCE=true
FRONTEND_URL=http://localhost:5173
```

Set `BILLING_ENFORCE=false` to disable paywall in local dev without Stripe.

## Event destination (webhooks)

In Stripe Dashboard → **Developers → Event destinations**:

| Setting | Value |
|--------|--------|
| **Scope** | **Your account** (not Connected accounts unless you use Connect) |
| **API version** | `2026-04-22.dahlia` |
| **Endpoint URL** | `https://<your-api-host>/billing/api/webhook/` |

### Recommended events (Selected events)

Subscribe only to what the app handles (`billing/webhook_handlers.py`):

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Optional (not required today):

- `customer.subscription.trial_will_end` — email reminders
- `payment_intent.succeeded` / `payment_intent.payment_failed` — only if you add one-off PaymentIntents later

You do **not** need “All events” for maintainability.

### Local testing

```bash
stripe listen --forward-to localhost:8000/billing/api/webhook/
```

Use the printed `whsec_...` as `STRIPE_WEBHOOK_SECRET` (restart Django after changing it).

**400 Invalid signature:** `STRIPE_WEBHOOK_SECRET` does not match the sender. Local CLI (`stripe listen`) and Dashboard event destinations use **different** secrets — only one should hit your machine, with the matching `whsec_...` in `.env`.

**Checkout lands on `localhost:3000` / connection refused:** set `FRONTEND_URL` to your Vite dev server (default `http://localhost:5173`) and restart the API, or pass `success_url` / `cancel_url` from the frontend (FleetFlow does this when starting checkout from the app).

## Customer Portal

Enable the [Customer Portal](https://dashboard.stripe.com/settings/billing/portal) so fleet owners can update cards and cancel from **Settings → Billing**.
