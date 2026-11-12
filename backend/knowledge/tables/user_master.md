---
okf_version: "0.2"
type: table_schema
id: table_user_master
table: user_master
scope: shared
primary_key: user_id
retrieval_hints:
  standalone_queries:
    - "user count"
    - "user roles/access"
    - "client user list"
  requires_join_with:
    - client_master (via client_id)
    - executive_master (via executive_id)
    - contact_sync_corp (via user_id)
    - contact_sync_sir (via user_id)
relationships:
  - column: client_id
    references: client_master.client_id
    type: many_to_one
    description: Links user to their client/organization
  - column: executive_id
    references: executive_master.executive_id
    type: many_to_one
    description: Links user to their executive/staff record
  - column: user_id
    references: contact_sync_corp.user_id
    type: one_to_many
    description: User can have multiple corporate contact sync records
  - column: user_id
    references: contact_sync_sir.user_id
    type: one_to_many
    description: User can have multiple SIR contact sync records
---
# user_master

Purpose: Application users, roles, client assignments and access.
Columns: `user_id`, `visit_count`, `user_flag`, `client_id`, `role_id`, `mobileno`, `password`, `expirydate`, `party_id`, `ac_nos`, `designation_id`, `ac_no`, `vehicles`, `is_approved`, `user_ac_no`, `user_list_no`, `user_voter_id`, `booth_ids`, `user_idcard_number`, `executive_id`, `is_active`, `deactive_by`, `deactive_date`, `total_contact_count`, `super_admin_id`, `user_shifted_report_flag`, `user_survey_data_flag`, `user_objection_report_flag`, `survey_data_download_flag`, `pwa_user`, `export_options_flag`, `booth_voting_sync_flag`, `app_version`.
Rules: PK=`user_id`. `client_id`→`client_master.client_id`; `executive_id`→`executive_master.executive_id`. `user_flag` C/A meanings unconfirmed. `ac_nos`/`booth_ids`=collections. `ac_no`≠`user_ac_no`; `user_list_no`, `user_voter_id`, `user_idcard_number` distinct. Never select `password`.
