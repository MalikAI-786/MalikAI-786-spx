# MalikAI-786 SPX 0DTE System — Independent Audit Memo
**Auditor:** Yasir A. Malik (self-audit as system owner, IIA-style)
**Engagement period:** v4.1 production → v5.0 redesign
**Date issued:** May 28, 2026
**Status:** Draft for owner review

---

## 1. Executive Summary

The MalikAI-786 SPX 0DTE Morning Bias System (v4.1) is a personal-use, educational, signal-generation pipeline that produces a directional bias score for SPX 0-day-to-expiration options each US trading day at 9:30 AM ET, distributed by email to one primary recipient and seven blind-copied recipients. A companion close-of-day report logs synthetic outcomes to a rolling ledger.

This audit was triggered by (a) a material change in the owner's employment status (the owner is no longer employed at Citi as of late May 2026 and has filed for state unemployment benefits) and (b) the planned v5.0 redesign which introduces three AI cross-check sources (Codex, Gemini, Perplexity) in place of two human peer models (Angelo, Omeir), a self-improving feedback loop ingesting prior-day close outcomes, and a public transparency dashboard on GitHub Pages.

**Overall conclusion:** the system is **operationally functional** but has **four findings** that must be remediated before v5.0 production deployment to avoid potential regulatory exposure and to protect the owner's professional brand during job-search. None of the findings, taken individually, indicates the system *currently* operates as an unregistered investment advisory business; the cumulative posture, however, materially affects how it must be presented and framed.

| Finding | Severity | Rating |
|---|---|---|
| F-01: Holding-out risk under Investment Advisers Act of 1940 §202(a)(11) | High | Significant Deficiency |
| F-02: Distribution-list framing creates "advice" inference | Medium | Control Gap |
| F-03: Unemployment-benefit reporting interaction | Medium | Control Gap |
| F-04: Missing audit trail / git provenance / immutable ledger | Medium | Control Gap |
| F-05: AI source attribution + model risk under SR 11-7 analogy | Low-Medium | Observation |
| F-06: Crypto module (planned) introduces CFTC / state MTL surface | Low (planned) | Observation |

---

## 2. Scope and Methodology

**In scope:**
- The morning-bias scheduled task (`SKILL.md` v4.1 → v5.0)
- Email distribution (`gmail_send.py` via OAuth, 8 recipients)
- Local ledger and SPX-Reports artifacts
- Public dashboard published at `malikai-786.github.io/malikai-spx-dashboard/`
- Planned v5.0 changes: 3 AI sources, self-improving loop, paper-trade ledger
- Planned crypto module v1 (signal-paste, manual execution)

**Out of scope:**
- The owner's actual brokerage accounts (Option Alpha, Tastytrade) — the system generates *signals*, not orders, and does not connect to trading APIs
- Tax planning (referenced only where directly relevant)
- The owner's separate Citi-era restricted lists or pre-clearance obligations (no longer applicable)

**Approach:** documentary review of the SKILL.md spec; review of the actual email sent at 09:18 ET on May 28, 2026 (message_id `19e6ebc7c5ee0add`); walk-through of the gmail_send.py code; mapping each touchpoint to the applicable regulatory framework. Standards referenced: IIA International Standards for the Professional Practice of Internal Auditing, COSO 2013, SR 11-7 (model risk), SEC Investment Advisers Act of 1940, FINRA Rule 2010, CFTC Reg 4.13, IRS §6045, and relevant state guidance.

---

## 3. Regulatory Framework Tagging

Every operational touchpoint and the framework that governs it:

| Touchpoint | Primary framework | Secondary framework | Trigger condition |
|---|---|---|---|
| Generating a directional signal | None (private speech) | First Amendment editorial | Becomes regulated when offered for compensation or held out as professional advice |
| Emailing signal to self | None | — | — |
| Emailing signal to BCC list (7 people) | Investment Advisers Act of 1940 §202(a)(11) | Anti-fraud Rule 206(4) | Triggered if (a) compensation flows OR (b) holding out as adviser OR (c) general public solicitation |
| Public GitHub dashboard | Investment Advisers Act §203(a) registration | SEC Marketing Rule 206(4)-1 | Triggered if performance claims, testimonials, or hypothetical results presented without disclaimers |
| Synthetic / hypothetical P&L on dashboard | SEC Marketing Rule 206(4)-1(d)(2) | Rule 156 (investment company advertising) | Hypothetical performance must be accompanied by required disclosures even if no registration |
| AI source attribution (Codex, Gemini, Perplexity) | SR 11-7 (model risk mgmt, by analogy) | EU AI Act Art. 50 transparency | Independent validation, version control, and documented limitations required |
| Crypto module (planned) | CFTC Reg 4.13 (commodity pool) | State money transmitter licensing | Triggered only if pooled capital or facilitating others' transactions |
| Daily P&L recording | IRS §6045 broker reporting | §1256 mark-to-market for SPX | Owner remains responsible for personal tax accounting — system does not constitute books-of-record |
| Email broadcast operationally | CAN-SPAM Act 15 USC §7704 | — | Must include physical postal address + unsubscribe — currently has "Reply remove" only |
| OAuth handling of Gmail tokens | NIST SP 800-63 digital identity | — | Token at `~/.gmail-mcp/token.json` must remain locked-down (chmod 600) |
| Unemployment benefit eligibility | State unemployment insurance law | Federal UC laws | Income from this activity may be reportable — see F-03 |

---

## 4. Findings and Recommendations

### F-01 (HIGH): Holding-out risk under Investment Advisers Act of 1940 §202(a)(11)

**Observation.** The current email subject line ("SPX 0DTE Morning Bias — Score …") combined with the inclusion of explicit click-by-click execution instructions on two real brokerages (Option Alpha, Tastytrade) and a phone-fallback script could be construed, by a reasonable recipient or by SEC staff, as the owner *holding himself out* as an investment adviser. The "Reply 'remove' to be removed from this list" language reinforces a managed-distribution / subscription character. Even though no compensation currently flows, holding-out alone can satisfy the §202(a)(11) definitional test.

**Risk if unremediated.** Cease-and-desist letter, registration order, civil penalties, and — given the owner is between jobs and rebuilding a professional brand — significant reputational impact at exactly the wrong moment.

**Recommendation.**
1. Reframe the deliverable as **"market education content"** rather than "trade recommendations." Replace "Trade at 9:45 ET" in subject lines with "Educational market analysis — published 9:30 ET."
2. Strip click-by-click execution instructions from the email body. Move them behind an explicit gate on the dashboard: *"If you are a self-directed trader who has already decided to take this view, here is how the owner himself would structure the position."*
3. Replace the recipient distribution with a **pull model**: subscribers visit the public dashboard. The email becomes the owner's own log, with optional self-CC.
4. Add a permanent footer disclaimer to every artifact: *"Educational content only. The author is not a registered investment adviser. Past simulated performance is not indicative of future results. You are responsible for your own trading decisions."*
5. Document a written **"Not Investment Advice" policy** in the repo and link it from every email and every dashboard page.

### F-02 (MEDIUM): Distribution-list framing creates "advice" inference

**Observation.** Seven named individuals receive the email by BCC. Several names suggest family/friends (e.g., recipients sharing the owner's surname / spouse correspondence). A regulator presented with this list would observe that the owner has effectively built a managed subscriber base, even informally.

**Recommendation.**
1. Convert the BCC list to a public mailing list with explicit opt-in via the dashboard (e.g., Buttondown, ConvertKit, or a simple Mailchimp). This creates an auditable trail of subscriber consent.
2. Add CAN-SPAM-compliant footer: owner's mailing address (or PO Box) + one-click unsubscribe link.
3. Until the public list is live, **scope distribution down to the owner only** and label the email "personal trading journal."

### F-03 (MEDIUM): Unemployment-benefit reporting interaction

**Observation.** The owner has filed for unemployment benefits. In most US states, any income — including income from self-employment activities such as paid newsletters, consulting, or trading advisory services — must be reported on each weekly certification. Even non-monetized "work activity" can affect eligibility if the state interprets it as "self-employment."

**Recommendation.**
1. Until the SPX system is monetized, treat it as **personal portfolio research and skill-building** — generally an allowable activity in most states (analogous to studying for a certification).
2. Do not accept payments, donations, Patreon, or affiliate-link commissions from the dashboard while drawing benefits. If any compensation appears, report it on the next weekly certification and consult the state UI office in writing.
3. Add a "Compliance Status" line to the repo README: *"Currently personal research only. No compensation. No advisory relationship. Confirmed compatible with unemployment claim filed [date] in state of [XX] as of [date]."*
4. Owner should call the state UI office once to confirm posture in writing (email or recorded note). This becomes the audit evidence.

### F-04 (MEDIUM): Missing audit trail / git provenance / immutable ledger

**Observation.** v4.1 writes the morning report and ledger to local disk. There is no immutable provenance — the owner could (intentionally or not) edit historical scores after the fact, which would invalidate any performance claims. The fact that v5.0 introduces a public dashboard makes this control material.

**Recommendation.**
1. All morning reports, close reports, and ledger updates must be **committed to git on creation**, with a signed commit (GPG) and a content-hash recorded.
2. The dashboard must surface the **git commit hash** of the report on display, with a link to the source on GitHub.
3. The ledger CSV must be **append-only** — enforce via a pre-commit hook that rejects any commit modifying past rows.
4. A daily **provenance snapshot** (SHA-256 of the ledger) should be written to a public location (the dashboard's `/integrity` page) so any subscriber can verify the chain.

### F-05 (LOW-MEDIUM): AI source attribution under SR 11-7 model risk management (by analogy)

**Observation.** v5.0 introduces three AI peer cross-checks. By bank-grade model risk standards (SR 11-7), each model is a separate "model" requiring independent validation, documented assumptions, and version pinning. This is overkill for personal use but matters because a future bank/regtech employer reviewing the GitHub will judge the rigor of the documentation.

**Recommendation.**
1. Each of Codex / Gemini / Perplexity gets a one-page **Model Card** in `/repo/sources/`: vendor, model version, knowledge cutoff, known limitations, prompt template, intended use, out-of-scope use.
2. Pin the model version and prompt template in the SKILL.md so the same prompt can be re-run later for reproducibility.
3. Log every AI source response verbatim (under `/repo/sources/responses/{date}-{model}.md`) so the audit trail shows what each model said vs. what the composite did.
4. Add a **disagreement flag**: when 2 of 3 AI sources disagree with the primary model, confidence is automatically downgraded.

### F-06 (LOW, PLANNED): Crypto module CFTC / state MTL surface

**Observation.** The planned crypto module (v1) keeps execution manual — owner pastes a signal, system validates and shows the trade ticket, owner clicks the broker themselves. As long as no funds are pooled and no compensation flows, this remains personal-use.

**Recommendation.**
1. Hard-code in the crypto module spec: **"No auto-trading. No pooled funds. No compensation. No execution on behalf of others."**
2. Document the signal source (Telegram/Discord channel) and obtain a screenshot or copy of the channel's own terms of service to confirm signal use is permitted.
3. Add the same non-advice disclaimer to all crypto outputs.

---

## 5. Ethics Posture

Beyond the regulatory checklist, three ethical guardrails are embedded in the v5.0 design:

1. **Truthfulness over flattery.** When the model is wrong, the dashboard shows it. The rolling P&L tab will show losing days as prominently as winning days, including the largest drawdown ever logged. The owner does not get to delete bad days.
2. **No survivorship bias.** Every signal that fired is logged, including stand-downs. The synthetic P&L treats stand-downs as $0, which is the honest representation.
3. **Reader-aligned incentives.** Until and unless the owner formally registers, the system is presented as a learning artifact — *"this is what I'm building; here's my work; copy at your own risk."*

---

## 6. Controls Map (post-remediation)

| Control ID | Control description | Frequency | Evidence |
|---|---|---|---|
| C-01 | Non-advice disclaimer present on every email + every dashboard page | Continuous | Static footer template |
| C-02 | Git commit hash recorded in each report header | Daily | Auto-injected by `scripts/morning.py` |
| C-03 | Ledger CSV append-only (no row mutation) | Daily | Pre-commit hook rejects rewrites |
| C-04 | Daily SHA-256 of ledger published | Daily | `/dashboard/integrity/` |
| C-05 | AI source responses logged verbatim | Daily | `/sources/responses/{date}-{model}.md` |
| C-06 | Confidence downgrade when 2/3 AI sources disagree | Per-run | `scoring.py` invariant |
| C-07 | No compensation flows; no payment processor connected | Continuous | Stripe / Patreon absence confirmed in CI |
| C-08 | OAuth token file permissions 600 | Daily | `scripts/preflight.sh` |
| C-09 | Distribution list capped at owner-only until public list launched | Continuous | Hard-coded in `gmail_send.py` |
| C-10 | Stand-down counted as $0 in rolling P&L (no survivorship) | Daily | `ledger/close.py` invariant |

---

## 7. Sign-off

This memo will be checked into `/repo/audits/AUDIT-MEMO-v5.0.md` and re-reviewed quarterly. Material changes to the system (new sources, new distribution channels, monetization events) trigger an interim review.

*Yasir A. Malik, system owner and self-auditor*
*May 28, 2026*

---

**Hazrat Ali (RA):** *"Do not let your difficulty in finding the right path stop you from walking it."*
The hardest audits are the ones we run on ourselves. This is the walk.
