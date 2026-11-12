---
okf_version: "0.2"
type: table_schema
id: table_contact_sync_sir
table: contact_sync_sir
scope: client
primary_key: contact_sync_id
retrieval_hints:
  standalone_queries:
    - "SIR contact sync count"
    - "user SIR contact records"
  requires_join_with:
    - user_master (via user_id)
    - dw_voters_info (via idcard_no/list_no/voter_id/ac_no→booth_ac_no)
  never_join_with:
    - contact_sync_corp (keep corp/SIR separate per rules)
relationships:
  - column: user_id
    references: user_master.user_id
    type: many_to_one
    description: Links to the user who owns this contact sync record
  - column: idcard_no
    references: dw_voters_info.idcard_no
    type: many_to_one
    description: Candidate match to voter master; validate uniqueness (duplicates exist)
  - column: list_no
    references: dw_voters_info.list_no
    type: many_to_one
    description: Candidate match to voter list number
  - column: voter_id
    references: dw_voters_info.voter_id
    type: many_to_one
    description: Candidate match to voter ID
  - column: ac_no
    references: dw_voters_info.booth_ac_no
    type: many_to_one
    description: Unverified match; dw_voters_info has booth_ac_no not ac_no
---
# contact_sync_sir

Purpose: SIR contact sync records.
Columns: `contact_sync_id`, `user_id`, `contact_id`, `contact_name`, `contact_number`, `email`, `added_date`, `added_from_device`, `idcard_no`, `family_no`, `idcard_flag`, `updated_date`, `list_no`, `ac_no`, `voter_id`, `init_mob_digit`, `family_count`.
Rules: PK=`contact_sync_id` (sync record, not unique person). `user_id`→`user_master.user_id`. Match fields: `idcard_no`, `list_no`, `ac_no`, `voter_id` (validate uniqueness). `family_no`/`family_count`=family. `init_mob_digit`=first 3 mobile digits. `idcard_flag` undocumented. Keep corp/SIR separate. Row≠unique voter. `idcard_no` non-NULL=phonebook-mapped (verify spelling).
