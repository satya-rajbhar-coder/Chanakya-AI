---
okf_version: "0.2"
type: table_schema
id: table_dw_voters_info
table: dw_voters_info
scope: client
primary_key: voter_cd
retrieval_hints:
  standalone_queries:
    - "voter count"
    - "voter demographics"
    - "status_type filter"
    - "booth/ward/assembly analysis"
  requires_join_with:
    - contact_sync_corp (via idcard_no/list_no/voter_id)
    - contact_sync_sir (via idcard_no/list_no/voter_id)
    - activity_details_corp (via idcard_no)
    - activity_details_sir (via idcard_no)
  never_join_with:
    - voter_details_corp (no ac_no column; booth_ac_no unverified)
    - Booth_Master (unavailable)
    - society_master (unknown)
    - sublocation_master (unknown)
relationships:
  - column: idcard_no
    references: contact_sync_corp.idcard_no
    type: one_to_many
    description: Voter can have multiple corporate contact sync records (candidate match)
  - column: idcard_no
    references: contact_sync_sir.idcard_no
    type: one_to_many
    description: Voter can have multiple SIR contact sync records (candidate match)
  - column: idcard_no
    references: activity_details_corp.idcard_no
    type: one_to_many
    description: Voter can have multiple corporate activity records (candidate match)
  - column: idcard_no
    references: activity_details_sir.idcard_no
    type: one_to_many
    description: Voter can have multiple SIR activity records (candidate match)
  - column: list_no
    references: contact_sync_corp.list_no
    type: one_to_many
    description: Voter list number to corporate contact sync
  - column: list_no
    references: contact_sync_sir.list_no
    type: one_to_many
    description: Voter list number to SIR contact sync
  - column: voter_id
    references: contact_sync_corp.voter_id
    type: one_to_many
    description: Voter ID to corporate contact sync
  - column: voter_id
    references: contact_sync_sir.voter_id
    type: one_to_many
    description: Voter ID to SIR contact sync
  - column: booth_ac_no
    references: contact_sync_corp.ac_no
    type: one_to_many
    description: Unverified booth assembly number to contact sync ac_no
  - column: booth_ac_no
    references: contact_sync_sir.ac_no
    type: one_to_many
    description: Unverified booth assembly number to contact sync ac_no
  - column: booth_id
    references: Booth_Master.booth_id
    type: many_to_one
    description: Target schema unavailable; do not query target
  - column: survey_society_cd
    references: society_master.survey_society_cd
    type: many_to_one
    description: Target schema unknown
  - column: subloc_cd
    references: sublocation_master.subloc_cd
    type: many_to_one
    description: Target schema unknown
---
# dw_voters_info

Purpose: Electoral voter master: demographics, family, booth, survey and SIR mapping.
Columns: `voter_cd`, `voter_id`, `list_no`, `old_voter_id`, `surname`, `name`, `middlename`, `roomno`, `age`, `gender`, `panno`, `familyno`, `subloc_cd`, `sublocation_no`, `fullname`, `idcard_no`, `marnmar`, `marnmar_det`, `is_dead`, `mobileno`, `dob`, `ward_no`, `newvoter_id`, `fullname_prefix`, `oldmobileno`, `booth_id`, `data_flag`, `status_type`, `ulb`, `booth_ac_no`, `district_eng`, `district_mar`, `assembly_name_eng`, `assembly_name_mar`, `list_name_eng`, `list_name_mar`, `relative_fm_eng`, `relative_fm_mar`, `relative_f_eng`, `relative_f_mar`, `relative_l_eng`, `relative_l_mar`, `rln_type`, `survey_roomno`, `survey_society_name`, `survey_society_cd`, `survey_old_sf`, `survey_ward_no`, `survey_society_name_mar`, `survey_birthdate`, `survey_mobileno`, `sir_year`, `sir_listno`, `sir_voter_id`, `sir_acno`, `sir_votercd`, `mapped_sir`, `mapped_voter_id`, `mapped_list_no`.
Rules: PK=`voter_cd` (count for unique voters). Distinct IDs: `voter_id`, `list_no`, `old_voter_id`, `newvoter_id`, `mapped_voter_id`, `sir_voter_id`. `fullname`=English full name. Survey: use `survey_birthdate`/`survey_mobileno`. `marnmar`: M=Marathi, NM=non-Marathi (not marital). `marnmar_det` caste codes: M, PANJABI, G, MU, N, SH, S, O, NM. `panno`=assembly info (not tax PAN). `booth_ac_no`=booth assembly (not voter `ac_no`). `fullname_prefix`=partitioning (not assembly filter). `status_type`: D=Deleted, A=Addition, O=Original. Current voters: `status_type <> 'D'` (excludes NULL). Deleted: `status_type = 'D'`. Historical=clarify. `data_flag`=batch/month. `is_dead=0`≠alive. `mapped_sir=1`=mapped. `ward_no`=panel. `survey_society_name` for survey reports. DOB: exclude 1900. SIR cols: only for 2002. No `ac_no` column. Quote as `"dw_voters_info"`.
