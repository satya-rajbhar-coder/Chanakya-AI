---
okf_version: "0.2"
type: table_schema
id: table_voter_details_corp
table: voter_details_corp
scope: client
matching_key: "idcard_no + ac_no"
retrieval_hints:
  standalone_queries:
    - "corporation voter details"
    - "voter address/contact"
    - "colour code analysis"
  requires_join_with:
    - education_master (via education_id) - unspecified
    - profession_master (via profession_id) - unspecified
    - caste_master (via caste_id) - unspecified
    - society_master (via society_id) - unspecified
  never_join_with:
    - dw_voters_info (no ac_no column; booth_ac_no unverified)
relationships:
  - column: idcard_no
    references: dw_voters_info.idcard_no
    type: many_to_one
    description: Candidate match to voter master; cannot safely join (dw_voters_info lacks ac_no)
  - column: ac_no
    references: dw_voters_info.booth_ac_no
    type: many_to_one
    description: Unverified match; booth_ac_no is not a verified substitute for ac_no
  - column: education_id
    references: education_master.education_id
    type: many_to_one
    description: Lookup target unspecified
  - column: profession_id
    references: profession_master.profession_id
    type: many_to_one
    description: Lookup target unspecified
  - column: caste_id
    references: caste_master.caste_id
    type: many_to_one
    description: Lookup target unspecified
  - column: society_id
    references: society_master.society_id
    type: many_to_one
    description: Lookup target unspecified
---
# voter_details_corp

Purpose: Corporation-edited electoral records, contact/address, status and colour code.
Columns: `idcard_no`, `ac_no`, `list_no`, `voter_id`, `phone_number`, `date_of_birth`, `education_id`, `profession_id`, `colour_code`, `caste_id`, `new_address`, `society`, `flat_number`, `email_id`, `extra_info_3`, `extra_info_4`, `extra_info_5`, `added_by`, `added_date`, `updated_by`, `updated_date`, `mobile`, `family_number`, `education`, `recently_voted`, `is_dead`, `ward_no`, `society_id`, `floor`, `room_no`, `locked_but_survey`, `response`, `name_source_id`, `remark`, `last_sync_status`, `last_sync_by`, `last_sync_datetime`, `shifted`, `marnmar`, `marnmar_det`, `lby_flag`, `sms_flag`, `sms_updateddate`, `new_voter_id`, `family_marked`.
Rules: Match key: `idcard_no + ac_no`. `phone_number` ≠ `mobile`. `new_voter_id` ≠ `dw_voters_info.newvoter_id`. Lookups: `education_id`, `profession_id`, `caste_id`, `society_id` unspecified. Flags: `recently_voted`, `is_dead`, `locked_but_survey`, `shifted`, `lby_flag`, `sms_flag`, `family_marked` distinct; verify meanings. `extra_info_3/4/5` opaque. `ward_no`=panel. `colour_code`=executive-assigned colour.
Caution: Cannot join to `dw_voters_info` (no `ac_no`; `booth_ac_no` unverified).
