---
okf_version: "0.2"
type: table_schema
id: table_karyakarni_master_pollmatrix_new
table: karyakarni_master_pollmatrix_new
scope: shared
primary_key: karyakarni_id
retrieval_hints:
  standalone_queries:
    - "karyakarni list"
    - "personnel assignments"
  requires_join_with:
    - client_master (via client_id)
    - hitchintak_master_pollmatrix_new (via karyakarni_id)
    - dw_voters_info (via idcard_no/voter_id)
    - society_master (via survey_society_id) - unknown
relationships:
  - column: client_id
    references: client_master.client_id
    type: many_to_one
    description: Links karyakarni to their client/organization
  - column: karyakarni_id
    references: hitchintak_master_pollmatrix_new.karyakarni_id
    type: one_to_many
    description: Karyakarni can have multiple hitchintak records (verify semantics)
  - column: idcard_no
    references: dw_voters_info.idcard_no
    type: many_to_one
    description: Candidate match to voter master (unverified)
  - column: voter_id
    references: dw_voters_info.voter_id
    type: many_to_one
    description: Unverified voter ID match
  - column: survey_society_id
    references: society_master.survey_society_id
    type: many_to_one
    description: Target schema unknown
---
# karyakarni_master_pollmatrix_new

Purpose: Karyakarni/personnel and organizational assignments.
Columns: `karyakarni_id`, `karyakarta_category_id`, `district_id`, `ac_no`, `taluka_id`, `first_name`, `middle_name`, `last_name`, `mobile_no_1`, `mobile_no_2`, `designation_1`, `designation_2`, `designation_3`, `gender`, `date_of_birth`, `booth_id`, `ward_no`, `election_id`, `village_name`, `prabhag_name`, `prabhag_no`, `vibhag_no`, `party_id`, `idcard_no`, `is_active`, `added_by`, `added_date`, `updated_by`, `updated_date`, `deactive_by`, `deactive_date`, `deactive_reason`, `voter_id`, `vehicle`, `assigned_booth_ids`, `assigned_kendra_ids`, `ulb_id`, `client_id`, `super_admin_id`, `sector_or_area`, `sp_karyakarni_id`, `survey_society_name`, `survey_society_id`, `ref_karyakarni_id`, `sector_pramukh_ref_id`, `client_registration_id`.
Rules: PK=`karyakarni_id`. `client_id`→`client_master.client_id`. `voter_id` target unverified. `assigned_booth_ids`/`assigned_kendra_ids` format unconfirmed. `survey_society_id` target unknown. No `hitchintak_id` column.
