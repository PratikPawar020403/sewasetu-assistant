# -*- coding: utf-8 -*-
"""
Synthetic personas for the SewaSetu evaluation framework.

Each persona defines:
  - name, age, village, block, mobile, personality traits
  - what they want to do
  - what must be true in the database when the conversation ends
  - the role (citizen or officer)
"""

CITIZEN_PERSONAS = [
    {
        "id": "kamala_devi",
        "name": "Kamala Devi",
        "age": 68,
        "dob": "15/03/1958",
        "gender": "Female",
        "marital_status": "Widow",
        "village": "Kathoni",
        "block": "Sonari",
        "mobile": "9876500001",
        "bank_account": "123456789012",
        "ifsc": "SBIN0003077",
        "role": "citizen",
        "personality": (
            "A 68-year-old widow from Kathoni village. She speaks simply and "
            "respectfully, often using 'ji'. She is not tech-savvy but determined "
            "to apply for the pension she heard about at the gram panchayat."
        ),
        "scenario": "eligible_new_application",
        "goal": (
            "She wants to apply for the Old Age Pension. She is eligible (68, widow, "
            "no existing application). She should successfully submit an application."
        ),
        "assertions": [
            {
                "type": "application_exists",
                "mobile": "9876500001",
                "status": "PENDING",
                "description": "A PENDING application should exist for mobile 9876500001",
            },
        ],
    },
    {
        "id": "raju_borah",
        "name": "Raju Borah",
        "age": 55,
        "dob": "20/08/1971",
        "gender": "Male",
        "marital_status": "Married",
        "village": "Namti Gaon",
        "block": "Namti",
        "mobile": "9876500002",
        "bank_account": "987654321098",
        "ifsc": "UBIN0542341",
        "role": "citizen",
        "personality": (
            "A 55-year-old man who is eager to apply. He heard from a neighbour "
            "that pension is available and wants to try. He gets a bit impatient "
            "when told he's not eligible."
        ),
        "scenario": "underage_rejection",
        "goal": (
            "He wants to apply for pension but is only 55 — under the minimum age "
            "of 60. The system should tell him he is not eligible and NOT create an "
            "application."
        ),
        "assertions": [
            {
                "type": "no_application",
                "mobile": "9876500002",
                "description": "No application should exist for mobile 9876500002 (underage)",
            },
        ],
    },
    {
        "id": "harish_chandra",
        "name": "Harish Chandra Das",
        "age": 72,
        "dob": "05/01/1954",
        "gender": "Male",
        "marital_status": "Married",
        "husband_name": "",
        "village": "Borgaon Town",
        "block": "Borgaon",
        "mobile": "9876500003",
        "bank_account": "567890123456",
        "ifsc": "PUNB0123400",
        "role": "citizen",
        "personality": (
            "A 72-year-old retired schoolteacher. He already has a pending application "
            "and wants to check its status. He is polite and articulate."
        ),
        "scenario": "status_check",
        "goal": (
            "He wants to check the status of his existing pension application. "
            "He should get back the details of his pending application."
        ),
        "pre_setup": {
            "type": "create_application",
            "mobile": "9876500003",
            "data": {
                "applicant_name": "Harish Chandra Das",
                "dob": "05/01/1954",
                "gender": "Male",
                "marital_status": "Married",
                "village": "Borgaon Town",
                "block": "Borgaon",
                "bank_account": "567890123456",
                "ifsc": "PUNB0123400",
            },
        },
        "assertions": [
            {
                "type": "application_exists",
                "mobile": "9876500003",
                "status": "PENDING",
                "description": "Application for Harish Chandra should still be PENDING",
            },
        ],
    },
    {
        "id": "meera_bai",
        "name": "Meera Bai Gogoi",
        "age": 65,
        "dob": "12/07/1961",
        "gender": "Female",
        "marital_status": "Married",
        "village": "Rajapara East",
        "block": "Rajapara",
        "mobile": "9876500004",
        "bank_account": "111222333444",
        "ifsc": "HDFC0001234",
        "role": "citizen",
        "personality": (
            "A 65-year-old woman who already has an approved application and tries "
            "to apply again. She doesn't realize her pension is already approved."
        ),
        "scenario": "duplicate_check",
        "goal": (
            "She tries to apply again but already has an active (APPROVED) application. "
            "The system should inform her about the existing application and refuse "
            "to create a new one."
        ),
        "pre_setup": {
            "type": "create_approved_application",
            "mobile": "9876500004",
            "data": {
                "applicant_name": "Meera Bai Gogoi",
                "dob": "12/07/1961",
                "gender": "Female",
                "marital_status": "Married",
                "village": "Rajapara East",
                "block": "Rajapara",
                "bank_account": "111222333444",
                "ifsc": "HDFC0001234",
            },
        },
        "assertions": [
            {
                "type": "application_count",
                "mobile": "9876500004",
                "expected_count": 1,
                "description": "Only one application should exist (duplicate blocked)",
            },
        ],
    },
    {
        "id": "gopal_krishna",
        "name": "Gopal Krishna Sharma",
        "age": 70,
        "dob": "22/11/1955",
        "gender": "Male",
        "marital_status": "Married",
        "village": "Dhemaji Town",
        "block": "Dhemaji Pathar",
        "mobile": "9876500005",
        "bank_account": "999888777666",
        "ifsc": "BARB0DHEMAI",
        "role": "citizen",
        "personality": (
            "A 70-year-old who has a pending application and wants to withdraw "
            "it because he made an error in his bank details, then reapply with "
            "correct information."
        ),
        "scenario": "withdraw_and_reapply",
        "goal": (
            "He wants to withdraw his pending application and then submit a new "
            "one with corrected bank details."
        ),
        "pre_setup": {
            "type": "create_application",
            "mobile": "9876500005",
            "data": {
                "applicant_name": "Gopal Krishna Sharma",
                "dob": "22/11/1955",
                "gender": "Male",
                "marital_status": "Married",
                "village": "Dhemaji Town",
                "block": "Dhemaji Pathar",
                "bank_account": "000000000000",
                "ifsc": "BARB0DHEMAI",
            },
        },
        "assertions": [
            {
                "type": "application_exists",
                "mobile": "9876500005",
                "status": "WITHDRAWN",
                "description": "Old application should be WITHDRAWN",
            },
            {
                "type": "application_exists",
                "mobile": "9876500005",
                "status": "PENDING",
                "description": "New corrected application should be PENDING",
            },
        ],
    },
    {
        "id": "lakshmi_devi",
        "name": "Lakshmi Devi Baruah",
        "age": 62,
        "dob": "30/06/1964",
        "gender": "Female",
        "marital_status": "Widow",
        "village": "Khelua Chariali",
        "block": "Khelua",
        "mobile": "9876500006",
        "bank_account": "555666777888",
        "ifsc": "SBIN0009999",
        "role": "citizen",
        "personality": (
            "A 62-year-old widow who wants to check if she is eligible. "
            "She is cautious and wants to understand the process before applying. "
            "She asks many questions."
        ),
        "scenario": "eligibility_inquiry",
        "goal": (
            "She wants to check eligibility first, and if eligible, proceed to apply. "
            "She is eligible (62, no existing application)."
        ),
        "assertions": [
            {
                "type": "application_exists",
                "mobile": "9876500006",
                "status": "PENDING",
                "description": "Application should be created after eligibility check",
            },
        ],
    },
]

OFFICER_PERSONAS = [
    {
        "id": "officer_singh",
        "name": "BDO Rajendra Singh",
        "role": "officer",
        "personality": (
            "Block Development Officer for Sonari block. Efficient and thorough, "
            "processes applications methodically. Checks documents carefully before "
            "approving."
        ),
        "scenario": "approve_applications",
        "goal": (
            "Review the pending applications queue for Sonari block, view details "
            "of the first application, and approve it with an audit note."
        ),
        "assertions": [
            {
                "type": "status_changed_to",
                "status": "APPROVED",
                "block": "Sonari",
                "description": "At least one Sonari application should be APPROVED",
            },
        ],
    },
    {
        "id": "officer_dutta",
        "name": "BDO Priya Dutta",
        "role": "officer",
        "personality": (
            "Block Development Officer handling rejections. She identifies "
            "applications with incomplete or suspicious documents."
        ),
        "scenario": "reject_application",
        "goal": (
            "Review the pending queue, identify an application to reject, and "
            "reject it with a proper reason documented in the audit trail."
        ),
        "assertions": [
            {
                "type": "status_changed_to",
                "status": "REJECTED",
                "description": "At least one application should be REJECTED with a reason in audit",
            },
        ],
    },
    {
        "id": "officer_manager",
        "name": "District Manager Anil Kumar",
        "role": "officer",
        "personality": (
            "District Social Welfare Officer who monitors the overall dashboard. "
            "Wants a summary of the workload."
        ),
        "scenario": "dashboard_review",
        "goal": (
            "Check the dashboard statistics to understand the current workload, "
            "overdue applications, and block-wise distribution."
        ),
        "assertions": [
            {
                "type": "dashboard_accessed",
                "description": "Dashboard stats should have been retrieved successfully",
            },
        ],
    },
]

ALL_PERSONAS = CITIZEN_PERSONAS + OFFICER_PERSONAS
