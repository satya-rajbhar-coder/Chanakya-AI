---
okf_version: "0.2"
type: schema_index
id: db_schema_index
title: "Client DB schema index"
---
# Retrieval index

Purpose: compact schema knowledge for NL-to-PostgreSQL-SQL. Do NOT load all schema files into every prompt. Retrieve only the table files relevant to the question and `query_rules.md` for SQL generation.

## Table map

- `client_master`: client/election/config; shared; PK `client_id`.
- `executive_master`: staff/employment/executive; shared; PK `executive_id`.
- `user_master`: application users/access; shared; PK `user_id`.
- `hitchintak_master_pollmatrix_new`: hitchintak/contact/geography; shared; PK `hitchintak_id`.
- `karyakarni_master_pollmatrix_new`: personnel/organization; shared; PK `karyakarni_id`.
- `dw_voters_info`: voter master/demographics/survey/SIR; client; PK `voter_cd`.
- `voter_details_corp`: corporation edited-voter/address/colour; client; composite matching fields `idcard_no + ac_no`.
- `activity_details_corp`: corporate activities; client; PK `activity_detail_id`.
- `activity_details_sir`: SIR activities; client; PK `activity_detail_id`.
- `contact_sync_corp`: corporate phonebook/contact sync; client; PK `contact_sync_id`.
- `contact_sync_sir`: SIR phonebook/contact sync; client; PK `contact_sync_id`.

## Retrieval policy (MANDATORY)

1. **Identify** requested entities/metrics/filters from the question.
2. **Retrieve ONLY** the minimum table files directly referenced.
3. **Always retrieve `query_rules.md`** before producing SQL.
4. **NEVER** load `index.md` unless explicitly asked for schema overview.
5. **NEVER** load unrelated tables (e.g., `voter_details_corp` for a `dw_voters_info` question).
6. If required schema or relationship is absent, **ask for clarification** rather than guessing.

## Per-table retrieval hints

Each table file includes a `retrieval_hints` section in its YAML frontmatter:
- `standalone_queries`: query types answerable with ONLY this table + `query_rules.md`
- `requires_join_with`: tables needed for common JOIN queries (relationships are inline in each table's YAML)
- `never_join_with`: tables that should NOT be joined (documented anti-patterns)

**Use these hints to minimize file loads.** Table files are authoritative for listed columns, local business rules, and relationships (in YAML frontmatter).
