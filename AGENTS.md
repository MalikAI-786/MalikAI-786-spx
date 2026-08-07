# Instructions for AI agents

**Read the control center before you act.** These repositories are the
*published record*. They are deliberately not the current state of anything.
What is live, what is blocked, what was decided last week, and what is in
flight lives in one place:

### ▶ [Malik Operating System — the control center](https://www.notion.so/3b54ffd38c7e8183ad84fa2ca08c5c3c)

If you can reach Notion, open it first. If you cannot, say so plainly and work
only from what is in the repository — do not infer current status from a file's
contents or a commit date. A README describes intent; it is not a status
report.

## Order of authority

| Rank | Source | Holds |
| --- | --- | --- |
| 1 | The control center (Notion) | Live status, decisions, what is blocked, what is next |
| 2 | `AGENTS.md` in the repo you are working in | Rules for that codebase |
| 3 | The repo `README.md` | The public narrative. Generated — see below |

When two disagree, the higher rank wins, and say out loud that you found the
conflict.

## This repository

The ledger is **append-only**, and the integrity hashes exist so that a
prediction cannot be edited once the outcome is known. Do not rewrite a past
row, do not "correct" a historical call, and do not rebase away ledger history.
If a past entry is wrong, append a correction — that is the whole control.

The educational-use-only disclaimer is not boilerplate. It stays, in full, and
it does not get softened.

Emails are drafted, never sent.

## Safeguards

These are not preferences.

**1. Every file in these repositories is public.** There is no private
directory, no "internal" folder, and nothing is protected by being unlinked.
Before writing a file, assume a recruiter, a regulator, and a search engine
will read it.

**2. Never commit human-subjects research data.** The doctoral study runs under
**IRB-25-0462**. In `malik-research`, `data/` and `output/` are denied by
`.gitignore` and the exclusion is tested. Do not add exceptions, do not
`git add -f`, and do not paste participant responses into a file, an issue, a
commit message, or a README. If a file contains a participant response it is in
the wrong place, whatever the file extension says.

**3. Never commit secrets or personal records.** No credentials, tokens, API
keys, `.env` files, account numbers, addresses, or identity documents. Nothing
about legal matters, tenants, medical history, or family belongs in version
control. If you are unsure whether something qualifies, it does.

**4. Do not send, publish, or post as Yasir.** Draft freely; transmit nothing.
That covers email, LinkedIn, Substack, issues, PR comments, and anything that
leaves the machine. Sending is his decision every time, and prior approval for
one message is not approval for the next.

**5. Never invent a fact about him.** Not a date, a title, an employer, a
credential, a metric, or a research finding. The entire argument of his work is
that a claim is worth what its evidence is worth — a fabricated line in a
README does more damage here than in almost any other portfolio. If a fact is
missing, leave it out and say you left it out. Do not approximate a year. Do
not round a number up.

**6. Do not present research as further along than it is.** The DBA is in
progress. Nothing here is peer-reviewed, published, or replicated unless it
says so with a citation.

**7. Preserve the disclaimers.** `MalikAI-786-spx` and `index007.html` carry
educational-use-only language for a reason. It is not boilerplate to be tidied
away, and it does not get softened.

**8. Flag rather than fix, when the fix is a decision.** Renaming a repository,
deleting history, changing a public URL, force-pushing, or altering how he is
described professionally are his calls. Bring them to him.

## The brand is settled

Do not redesign it, and do not re-litigate the palette. It is documented at
[brand.html](https://malikai-786.github.io/brand.html), and the tokens are in
`assets/brand/tokens.css` in the site repository.

- Ember `#E0662E` is the anchor. **It can never carry body text on a light
  ground** — it measures 3.11:1, which fails WCAG AA. Use `#AD4317` on light
  and `#F58E5C` on dark.
- Warm graphite `#171A1D` on warm paper `#F6F3F0`. No cold greys.
- Verdigris `#0F5F5A` / `#4FC0B2` means *verified*. Ember means *priority*.
  They are never swapped.
- Charter for headlines, system sans for body, mono uppercase with wide
  tracking for labels.
- The descriptor is **Audit · Risk · Governance**. Not AI-forward, on purpose.

## Generated files

`README.md` in every repository on this account is generated from
`assets/brand/make_readmes.py` in the site repo, and so is this file. Editing
either one in place works until the next regeneration silently reverts it.
Change the manifest and regenerate.

The same applies to every image under `assets/brand/`: marks, banners,
avatars, the LinkedIn cover, the business card and the profile hero all come
out of `make_*.py` generators driven by one set of constants. Never hand-edit
an SVG or retouch a PNG — change the generator and re-run it.

---

<sub>[Profile](https://github.com/MalikAI-786) · [Site](https://malikai-786.github.io) · [Brand system](https://malikai-786.github.io/brand.html) · [Newsletter](https://proofoverpromise.substack.com) · [LinkedIn](https://linkedin.com/in/yasiramalik)</sub>

<sub><b>Yasir A. Malik</b> · Audit · Risk · Governance · Newark, NJ · NYC metro</sub>
