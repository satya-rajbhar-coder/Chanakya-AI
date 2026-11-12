---
okf_version: "0.2"
type: query_rules
id: db_query_rules
title: "SQL generation rules"
---
# SQL contract

Return exactly one JSON object: `{"title":"Short title","sql":"SELECT ...","reason":null}`. If unreliable: `{"title":"Short title","sql":null,"reason":"Concise explanation or one clarification question"}`. Use JSON null, not string "null".

- Output one read-only PostgreSQL `SELECT`, optionally with `WITH`; never multiple statements or data-changing SQL.
- Use only retrieved table files; never invent tables/columns/keys. Never `SELECT *`.
- Never select `client_key` or `password`.
- Use bare table names only; no schema/database prefix. Quote `dw_voters_info` as `"dw_voters_info"` if that is its actual PostgreSQL identifier.
- Qualify columns with aliases in joins. Avoid join fan-out; use `EXISTS`/pre-aggregation or `COUNT(DISTINCT verified_pk)` where needed. Never use DISTINCT to hide a bad join.
- `LEFT JOIN` preserves unmatched parents; `INNER JOIN` returns matched rows only.
- Voter counts: use `voter_cd` as unique voter-master key; ordinary current-voter filter is `status_type <> 'D'`, which also excludes NULL. For historical/all records, clarify if ambiguous.
- Activity counts: count `activity_detail_id`/activity records, not joined voter rows.
- Contact counts: count `contact_sync_id` unless a verified unique-person key exists.
- Add LIMIT only when requested or required by pagination. For top N, use ORDER BY + LIMIT N.
- Unknown status/flag codes remain unknown. Do not assume NULL means 0/false.
- Do not guess lookup tables or unresolved joins. If answer depends on missing schema/key/meaning, return `sql:null` and explain.
- SQL examples or literal values must be read-only. The target app's original contract says bind placeholders are unsupported; follow the executing app's parameterization/security design rather than interpolating untrusted input.
