# SPX morning data feed (structured sources)

Use these structured feeds for every number in the morning email. Use web
search only to explain *why* something moved (news), never as the source of a
price, close, VIX level or probability. Each call goes through the Firecrawl
Alexandria tool `alexandria_library_read`. One morning batch is 4 calls,
about 20 credits, in one request:

```json
[
  {"provider": "cnbc-com", "capability": "news/quotes",
   "options": {"symbols": [".SPX", ".VIX", "US10Y", ".N225", ".HSI", ".GDAXI", ".FTSE", "@CL.1"]}},
  {"provider": "cmegroup-com", "capability": "fomc-rate-probabilities/futures_quotes",
   "options": {"product_id": 133, "limit": 1}},
  {"provider": "forexfactory-com", "capability": "economic-calendar/list_events",
   "options": {"currencies": ["USD"], "date": "<YYYY-MM-DD today>", "impacts": ["high"], "view": "day"}},
  {"provider": "cmegroup-com", "capability": "fomc-rate-probabilities/fedwatch_meetings",
   "options": {}}
]
```

## What each field feeds

| Need | Field | Notes |
|---|---|---|
| Prior SPX close (scoring yesterday, strikes) | `.SPX` `last_value` (before the open) | CNBC has no date. Check that `last_time` shows the prior session's date. |
| VIX for sigma | `.VIX` `last_value` | Prior close before 9:30. |
| Futures bucket | ES front month `percentage_change`, `last`, `prior_settle` | Quotes are 10 minutes delayed. ES is not on CNBC, so use the CME call. |
| International bucket | `.N225`, `.HSI`, `.GDAXI`, `.FTSE` `change_percent` | Check `last_time`. An index printed with an old date or "UNCH" counts as partial coverage. |
| Macro bucket and binary gate | ForexFactory `events[]` `name`, `datetime_utc`, `forecast`, `previous` | Times are UTC; convert to ET. |
| Rates context | `US10Y` `last_value` (percent) | |
| Fed odds | `selected_meeting.probabilities_pct` (hike / no_change / ease) and `meeting_date` | CME FedWatch. |
| Oil | `@CL.1` `last_value`, `change_percent` | |

## Rules

- **Stale-data check:** compare `last_time` with today. An index that has not
  traded yet today (for example, the DAX before Frankfurt opens) shows the prior
  session. Say so and do not score it as today's move.
- **Holidays and half days:** if any feed is down, fall back to web search and
  mark that bucket PARTIAL. If the futures and VIX are both unavailable, STAND
  DOWN. US market holidays (Thanksgiving 2026-11-26 is closed) and half days
  (2026-11-27 closes at 1:00 PM ET, so the 0DTE expires at 1:00 PM) come from
  the NYSE calendar. On a half day, say so and use the shorter session.
- **Scoring yesterday:** use the CNBC `.SPX` `last_value` taken before the open
  (the official prior close). Cross-check `previous_close_value` the next day.
- After the run, optionally rate the batch with `firecrawl_feedback`. It refunds
  1 credit per call.
