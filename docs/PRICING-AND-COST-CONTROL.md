# GQMRMed pricing and cost control

## Current launch plans

| Plan | Price target | Duration | Generation allowance | Stars |
|---|---:|---:|---:|---:|
| FREE | $0 | ongoing | 1 design/day | — |
| PLUS | $15 | 30 days | 2 designs/day | 1,200 ⭐ |
| PRO | $50 | 90 days | 3 designs/day | 3,850 ⭐ |

The database migration `0018_openai_reference_pricing` is authoritative for live plan records. Existing paid subscriptions keep their already-issued expiry dates; the migration changes future entitlement resolution/purchases rather than retroactively shortening an active subscription.

## Design cost budget

The production path uses OpenAI GPT-Image-2 for the illustration layer at 1024×1536 with medium quality, then composes exact medical text locally. The reference design is encoded into the deterministic QMRMed renderer rather than uploaded with every job.

The planning budget is **$0.07 per completed design**:

- approximately $0.041 for a 1024×1536 medium GPT-Image-2 output;
- approximately $0.008–$0.010 for image prompt/input allowance;
- approximately $0.001–$0.003 for evidence-locked text synthesis allowance;
- approximately $0.010–$0.015 for storage, queue, delivery, retry and operational reserve.

This is a conservative fully-loaded planning ceiling, not a claim that every request bills exactly $0.07.

## Why FREE is 1/day

At the $0.07 planning ceiling, 3 free designs/day can create a variable-cost subsidy of about $6.30 over 30 days for a continuously active free account. One design/day reduces that theoretical subsidy to about $2.10 per 30 days while still providing a meaningful daily trial.

## Paid-plan safety envelope

At maximum theoretical use:

- PLUS: 60 designs / 30 days × $0.07 = **$4.20**, about 28% of the $15 headline price.
- PRO: 270 designs / 90 days × $0.07 = **$18.90**, about 38% of the $50 headline price.

This keeps the planned variable generation cost below the 40% target before fixed infrastructure, taxes, refunds and payment overhead.

## Design credit packs

| Pack | Credits | Stars | Approx. reward value at $0.013/Star |
|---|---:|---:|---:|
| DESIGN_5 | 5 | 60 ⭐ | $0.78 |
| DESIGN_12 | 12 | 120 ⭐ | $1.56 |
| DESIGN_20 | 20 | 180 ⭐ | $2.34 |

Telegram's developer reward value and the user's Star acquisition price are not the same thing; the latter can vary by region/platform. The bot therefore presents Stars as the invoice currency and does not promise a fixed USD purchase price for Stars.

## Operating rule

Do not increase quotas or lower prices until measured production data confirms that actual image cost, retries, storage, infrastructure and payment overhead remain within the target margin. If the image model or quality level changes, recalculate pricing before changing the public limits.
