# GQMRMed launch pricing and cost-control strategy

## Launch plans

| Plan | Price | Duration | Generation allowance |
|---|---:|---:|---:|
| FREE | $0 | ongoing | 3 designs/day |
| PLUS | $5 | 30 days | 8 designs/day |
| PRO | $20 | 90 days | 15 designs/day |

The paid plans intentionally do **not** use unlimited generation at launch. The existing usage ledger reserves one unit before a job is queued and commits it only after successful generation, so the daily ceilings are enforced atomically even under concurrent Telegram messages.

## Why this model

The first deployment should remain as close to zero fixed cost as possible. At the same time, paid users must not be able to create an unbounded variable-cost bill while the infrastructure is still small.

The launch model therefore uses:

1. a generous FREE entry point (3/day),
2. a low-friction PLUS plan for regular users,
3. a PRO plan for heavy users,
4. explicit fair-use ceilings,
5. durable usage accounting,
6. provider abstraction so image generation can move from a free/experimental GPU backend to a paid GPU only when demand justifies it.

## Cost coverage rule

Do not increase quotas or advertise unlimited use until real production metrics show that subscription revenue comfortably covers:

- AI text/research spend,
- image-generation/GPU spend,
- database/cache/storage costs,
- Telegram/hosting overhead where applicable,
- a safety margin for failed jobs and traffic spikes.

A practical operating target is to keep **variable compute + storage cost below 35–40% of paid subscription revenue** before adding more capacity or increasing quotas. This leaves room for infrastructure upgrades and unexpected spikes.

## Growth gates

### Stage 0 — launch at zero/near-zero fixed cost

Use the free infrastructure already selected for the project where technically viable. Keep ComfyUI/image generation replaceable and do not hard-wire the application to a paid GPU provider.

### Stage 1 — first paying users

Measure, at minimum:

- active users/day,
- designs/day,
- designs/user/day by plan,
- successful vs failed generations,
- average generation latency,
- AI tokens per design,
- image-generation cost per design,
- storage consumed,
- revenue per paid user,
- cost per paid user,
- gross contribution per plan.

### Stage 2 — sustained demand

Only when the free stack becomes the bottleneck, upgrade the single resource causing the bottleneck. Prefer upgrading the worker/GPU before unnecessarily paying for every component.

### Stage 3 — scale

Introduce a paid always-on worker/GPU and persistent production storage when the measured contribution margin supports it. Keep the API, bot, queue, database, and image provider independently replaceable.

## Pricing adjustment policy

Pricing is data-driven rather than permanent. The database plan records are deliberately mutable through migrations/admin tooling so we can later:

- raise or lower the price,
- change duration,
- change daily fair-use limits,
- add an annual plan only after real usage data supports it,
- introduce a higher-volume business/education plan if demand warrants it.

Existing paid subscriptions should retain their already-issued expiry dates. A pricing migration changes future plan purchases and newly generated activation codes; it does not retroactively shorten active subscriptions.

## Important launch decision

The previous `PLUS $5 / 30 days unlimited` and `PRO $20 / 365 days unlimited` proposal is intentionally replaced at launch by the capped plans above. Unlimited usage can be reconsidered after the system has measured real per-design cost and subscriber behavior.
