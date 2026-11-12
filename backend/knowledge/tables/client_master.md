---
okf_version: "0.2"
type: table_schema
id: table_client_master
table: client_master
scope: shared
primary_key: client_id
retrieval_hints:
  standalone_queries:
    - "client config"
    - "election/party info"
    - "client list"
  requires_join_with:
    - executive_master (via client_id)
    - user_master (via client_id)
    - hitchintak_master_pollmatrix_new (via client_id)
    - karyakarni_master_pollmatrix_new (via client_id)
relationships:
  - column: client_id
    references: executive_master.client_id
    type: one_to_many
    description: Client can have multiple executives
  - column: client_id
    references: user_master.client_id
    type: one_to_many
    description: Client can have multiple users
  - column: client_id
    references: hitchintak_master_pollmatrix_new.client_id
    type: one_to_many
    description: Client can have multiple hitchintak records
  - column: client_id
    references: karyakarni_master_pollmatrix_new.client_id
    type: one_to_many
    description: Client can have multiple karyakarni records
---
# client_master

Purpose: Client, election, party, application and database configuration.
Columns: `client_id`, `state_id`, `client_code`, `client_name`, `client_key`, `election_type_id`, `corporation_id`, `party_id`, `mobile_no1`, `email`, `photo`, `header_images`, `ac_nos`, `ward_nos`, `election_id`, `show_survey_data`, `host_name`, `db_name`, `centralized_flag`, `whatsapp_slip_photo`, `whatsapp_msg_eng`, `whatsapp_msg_mar`, `auto_login`, `is_active`, `election_ids`, `client_name_mar`, `show_lby_data`, `review_plus_flag`, `designation_id`, `client_registration_id`, `year`.
Rules: PK=`client_id`. `client_code`=text/numbers. `ac_nos`/`ward_nos`=JSON collections. `election_id`≠`election_ids`. Never select `client_key`. Flags=0/1; NULL≠0.
