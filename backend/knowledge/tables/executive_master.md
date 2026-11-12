---
okf_version: "0.2"
type: table_schema
id: table_executive_master
table: executive_master
scope: shared
primary_key: executive_id
retrieval_hints:
  standalone_queries:
    - "executive count"
    - "executive assignments"
    - "staff list by client"
  requires_join_with:
    - client_master (via client_id)
    - user_master (via executive_id)
    - activity_details_corp (via executive_id)
    - activity_details_sir (via executive_id)
relationships:
  - column: client_id
    references: client_master.client_id
    type: many_to_one
    description: Links executive to their client/organization
  - column: executive_id
    references: user_master.executive_id
    type: one_to_many
    description: Executive can have multiple users assigned
  - column: executive_id
    references: activity_details_corp.executive_id
    type: one_to_many
    description: Executive can have multiple corporate activity records
  - column: executive_id
    references: activity_details_sir.executive_id
    type: one_to_many
    description: Executive can have multiple SIR activity records
---
# executive_master

Purpose: Staff, assignments, employment and synchronization.
Columns: `executive_id`, `enquiry_id`, `full_name`, `first_name`, `middle_name`, `last_name`, `mobile_no`, `designation_id`, `executive_type`, `joining_date`, `leaving_date`, `mobile_no2`, `emp_status`, `client_id`, `birthdate`, `age`, `gender`, `area`, `email`, `address`, `election_id`, `weekoff`, `is_active`, `last_sync_status`, `last_sync_by`, `last_sync_datetime`.
Rules: PK=`executive_id`. `client_id`→`client_master.client_id`. `designation_id`, `executive_type`, `emp_status` codes undocumented.
