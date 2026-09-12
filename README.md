# GQMRMed Bot

GQMRMed is an independent Telegram medical infographic generation system.

## Project boundaries

- Fully independent from QMRMed and QMRMed-Bot.
- No Telegram Mini App.
- Separate backend, database, queue, AI/image pipeline, storage, subscriptions, payments, and admin panel.
- The Telegram bot accepts medical text, topics, images, and supported files and produces original 9:16 medical infographics.

## Core architecture

```text
Telegram User
  -> GQMRMed Bot
  -> API / Orchestrator
  -> User / Subscription / Usage checks
  -> Redis Queue
  -> Medical Research
  -> Evidence Validation
  -> Content Synthesis
  -> Visual Architect
  -> Image Generation (FLUX.2 Klein / ComfyUI)
  -> SVG/HTML exact-text rendering
  -> Medical QA + Visual QA
  -> Telegram final image
```

## Planned production modules

- Telegram bot (aiogram)
- FastAPI backend
- PostgreSQL + SQLAlchemy + Alembic
- Redis + worker queue
- Medical research and evidence validation
- Content synthesis and visual architecture selection
- ComfyUI / FLUX.2 Klein image generation
- SVG/HTML renderer for exact medical text and layout
- 9:16 medical design system
- Medical QA and visual QA
- Usage system: FREE = 3 designs/day
- PLUS = $5/month
- PRO = $20/year
- Activation codes
- Payment abstraction for Telegram Stars, external card payments, Zain Cash/manual verification
- Private web admin panel
- Storage, logging, monitoring, security, backups
- Automated tests, CI/CD, Docker, deployment and production hardening

## Build phases

1. Project foundation
2. Database
3. Subscription system
4. Activation codes
5. Usage system
6. Input handling
7. Input analyzer
8. Medical research engine
9. Evidence validation
10. Medical content synthesis
11. Visual architect
12. Visual design system
13. Medical illustration engine
14. Exact text rendering
15. Intelligent layout
16. Density and multi-page handling
17. Watermark
18. Medical QA
19. Visual QA
20. Quality gate
21. Job queue
22. Live progress
23. Final delivery
24. Failure handling and usage release
25. Storage
26. Payment system
27. Telegram Stars
28. External/manual payments
29. Plans
30. Admin panel
31. User management
32. Activation-code management
33. Payment management
34. Admin security
35. Logging
36. Monitoring
37. Security hardening
38. Testing
39. CI/CD
40. Docker
41. Deployment
42. Performance
43. Multi-GPU readiness
44. Backup and recovery
45. Retention policies
46. Final production release

## Status

Phase 1 — repository foundation initialized.
