# GQMRMed cost model and pricing — September 2026

## 1. Canonical generation path

The production design path is now deliberately split into two responsibilities:

```text
Medical topic
  -> PubMed / configured medical research
  -> evidence-locked synthesis
  -> deterministic visual architecture
  -> OpenAI GPT-Image-2 illustration layer
  -> deterministic QMRMed Arabic/English compositor
  -> 1024x1536 PNG
```

OpenAI is responsible for the creative illustration layer. It is **not** trusted to render the final medical text. The final cards, Arabic typography, labels, numbers, disclaimer and branding are rendered locally from validated structured content. This is what keeps the reference design stable across topics.

## 2. Per-design budget

The production budget is intentionally conservative rather than pretending that an API output price is the entire operating cost.

| Component | Planning cost / design |
| --- | ---: |
| GPT-Image-2, medium, 1024x1536 output | ~$0.041 |
| Image prompt/input-token allowance | ~$0.008–$0.010 |
| Medical synthesis / small text-model allowance | ~$0.001–$0.003 |
| Storage, queue, Telegram delivery, retries and operational reserve | ~$0.010–$0.015 |
| **Conservative fully-loaded budget** | **$0.07/design** |

OpenAI publishes GPT-Image-2 token pricing at $5/M text input, $8/M image input, and $30/M image output; its image-generation guide gives a 1024×1536 medium example of about $0.041 for the image output itself. The $0.07 number above is therefore a budgeting ceiling for pricing decisions, not a claim that every successful request costs exactly $0.07.

The reference image is encoded into the **design system**, not uploaded on every generation. That avoids paying an image-input charge for the master reference on every design.

## 3. Public subscription policy

The free allowance is intentionally reduced to **1 design/day**. This protects the service from a large free-user variable-cost burden while still giving new users a real daily trial.

| Plan | Price target | Duration | Daily designs | Maximum designs over term | Maximum variable-cost budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| FREE | $0 | ongoing | 1 | 1/day | ~$0.07/day subsidy |
| PLUS | $15 | 30 days | 2 | 60 | ~$4.20 |
| PRO | $50 | 90 days | 3 | 270 | ~$18.90 |

At the conservative $0.07/design budget, the theoretical variable-cost share is approximately **28% of PLUS revenue** and **38% of PRO revenue** before fixed infrastructure, taxes, refunds and payment/accounting overhead. This is deliberately safer than the previous $5/$20 plans, whose theoretical maximum usage could exceed a sustainable variable-cost envelope.

## 4. Telegram Stars

Telegram's Bot Developer Terms currently state a developer reward value of **$0.013 per earned Star**, while also stating that the user acquisition price of Stars can vary by region/platform and is not the same thing as the reward value.

Therefore the launch prices use rounded Star amounts:

| Product | Stars | Current reward-value reference | Designs | Approx. reward value/design |
| --- | ---: | ---: | ---: | ---: |
| PLUS | 1,200 ⭐ | $15.60 | up to 60 | ~$0.26 |
| PRO | 3,850 ⭐ | $50.05 | up to 270 | ~$0.19 |
| 5-design pack | 60 ⭐ | $0.78 | 5 | ~$0.16 |
| 12-design pack | 120 ⭐ | $1.56 | 12 | ~$0.13 |
| 20-design pack | 180 ⭐ | $2.34 | 20 | ~$0.12 |

The bot must not promise users that a particular number of Stars equals a fixed USD purchase price. The user-facing invoice is in `XTR`, and the exact Star acquisition price is controlled by Telegram and can vary by user/region.

## 5. Why FREE is 1/day

A fully active free user at 3 designs/day could consume roughly $6.30 of annualized variable generation budget every 30 days of continuous use, before fixed infrastructure. Reducing the free allowance to one design/day caps that subsidy at roughly $2.10 per 30-day period per continuously active free account.

The free tier is therefore a product-acquisition allowance, not an unlimited demonstration of the paid quota economics.

## 6. Cost-control rules

1. OpenAI GPT-Image-2 medium is the default creative artwork model.
2. The reference image is not resent per job; its visual DNA is encoded in the design system and deterministic renderer.
3. Exact medical text is never delegated to the image model.
4. Failed generations release the reserved usage unit.
5. The paid plan limits are enforced server-side in PostgreSQL.
6. Purchased credit packs remain independent of subscription duration.
7. Any future move to high-quality image generation must trigger a new cost review before changing public quotas/prices.
8. If actual billed image cost rises above the $0.07 planning ceiling, pricing/quotas must be recalculated before expanding limits.
