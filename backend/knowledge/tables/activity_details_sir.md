---
okf_version: "0.2"
type: table_schema
id: table_activity_details_sir
table: activity_details_sir
scope: client
primary_key: activity_detail_id
retrieval_hints:
  standalone_queries:
    - "SIR activity count"
    - "executive SIR activity log"
  requires_join_with:
    - executive_master (via executive_id)
    - dw_voters_info (via idcard_no)
  never_join_with:
    - activity_details_corp (keep corp/SIR separate per rules)
relationships:
  - column: executive_id
    references: executive_master.executive_id
    type: many_to_one
    description: Links activity to the executive who performed it
  - column: idcard_no
    references: dw_voters_info.idcard_no
    type: many_to_one
    description: Candidate match to voter master; duplicates cause bad joins
---
# activity_details_sir

Purpose: SIR workflow activity records.
Columns: `activity_detail_id`, `activity_id`, `executive_id`, `visit_datetime`, `last_sync_status`, `last_sync_by`, `last_sync_datetime`, `screen_name`, `idcard_no`.
Rules: PK=`activity_detail_id`. `executive_id`→`executive_master.executive_id`. `activity_id` 1–13 unmapped. Use `screen_name` for screens. Keep SIR/corp separate. `idcard_no`=candidate voter match (duplicates cause bad joins).
