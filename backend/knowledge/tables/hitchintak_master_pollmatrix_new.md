---
okf_version: "0.2"
type: table_schema
id: table_hitchintak_master_pollmatrix_new
table: hitchintak_master_pollmatrix_new
scope: shared
primary_key: hitchintak_id
retrieval_hints:
  standalone_queries:
    - "hitchintak list"
    - "booth/ward assignments"
  requires_join_with:
    - client_master (via client_id)
    - karyakarni_master_pollmatrix_new (via karyakarni_id)
    - dw_voters_info (via idcard_no)
relationships:
  - column: client_id
    references: client_master.client_id
    type: many_to_one
    description: Links hitchintak to their client/organization
  - column: karyakarni_id
    references: karyakarni_master_pollmatrix_new.karyakarni_id
    type: many_to_one
    description: Links to karyakarni; verify semantics before join
  - column: idcard_no
    references: dw_voters_info.idcard_no
    type: many_to_one
    description: Candidate match to voter master (unverified)
---
# hitchintak_master_pollmatrix_new

Purpose: Hitchintak, contact and geographic assignments.
Columns: `hitchintak_id`, `karyakarta_category_id`, `district_id`, `ac_no`, `taluka_id`, `first_name`, `middle_name`, `last_name`, `mobile_no_1`, `mobile_no_2`, `designation_1`, `designation_2`, `designation_3`, `gender`, `date_of_birth`, `booth_id`, `ward_no`, `election_id`, `village_name`, `prabhag_name`, `prabhag_no`, `vibhag_no`, `party_id`, `idcard_no`, `is_active`, `added_by`, `added_date`, `updated_by`, `updated_date`, `deactive_by`, `deactive_date`, `deactive_reason`, `karyakarni_id`, `client_id`, `super_admin_id`, `ref_hitchintak_id`, `client_registration_id`, `auto_inc_id`.
Rules: PK=`hitchintak_id`. `client_id`→`client_master.client_id`. `karyakarni_id`→`karyakarni_master_pollmatrix_new.karyakarni_id` (verify semantics). `taluka_id` often NULL. `ward_no`, `prabhag_no`, `vibhag_no` distinct.
