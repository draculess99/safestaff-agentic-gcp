import pytest
from app.agent import StaffingPlan, _validate_and_correct_plan

@pytest.mark.parametrize("demand, expected_supervisors, expected_total", [
    (0, 0, 0),     # demand: 0, supervisors: ceil(0/5)=0, total: 0+0=0
    (1, 1, 2),     # demand: 1, supervisors: ceil(1/5)=1, total: 1+1=2
    (5, 1, 6),     # demand: 5, supervisors: ceil(5/5)=1, total: 5+1=6
    (6, 2, 8),     # demand: 6, supervisors: ceil(6/5)=2, total: 6+2=8
    (42, 9, 51),   # demand: 42, supervisors: ceil(42/5)=9, total: 42+9=51
    (100, 20, 120), # demand: 100, supervisors: ceil(100/5)=20, total: 100+20=120
])
def test_validation_math(demand, expected_supervisors, expected_total):
    plan = StaffingPlan(
        shift_date="2026-08-25",
        predicted_demand=0,
        direct_care_staff=0,
        registered_nurses=0,
        supervisors_required=0,
        recommended_staff=0,
        rationale="Initial plan",
        compliance_notes=[],
        validation_status=""
    )
    
    corrected = _validate_and_correct_plan(plan, demand)
    
    assert corrected.predicted_demand == demand
    assert corrected.direct_care_staff == demand
    assert corrected.supervisors_required == expected_supervisors
    assert corrected.recommended_staff == expected_total
    # RNs must always be at least 10
    assert corrected.registered_nurses == 10
    assert corrected.validation_status == "Corrected by deterministic rules"

def test_rn_validation_preserves_higher_counts():
    plan = StaffingPlan(
        shift_date="2026-08-25",
        predicted_demand=0,
        direct_care_staff=0,
        registered_nurses=15, # Gemini returns 15 RNs
        supervisors_required=0,
        recommended_staff=0,
        rationale="Initial plan",
        compliance_notes=[],
        validation_status=""
    )
    
    corrected = _validate_and_correct_plan(plan, 42)
    
    # Should not lower RN count if >= 10
    assert corrected.registered_nurses == 15
