import copy, json
from pathlib import Path
import pytest
from packages.phase2_design import load_catalog, validate_catalog, compile_opening_plan, REQUIRED_BOUNDARIES
ROOT=Path(__file__).resolve().parents[1]

def cat(): return load_catalog(ROOT/'docs/phase2/capability-catalog.json')

def test_catalog_is_design_only_and_complete():
    r=validate_catalog(cat()); assert r.valid, r.reasons; assert r.capability_count==16; assert r.waves==tuple(range(1,10)); assert not r.implementation_allowed

def test_every_capability_crosses_all_phase1_boundaries():
    for c in cat()['capabilities']: assert set(c['boundaries'])==set(REQUIRED_BOUNDARIES)

def test_missing_boundary_fails_closed():
    c=copy.deepcopy(cat()); c['capabilities'][0]['boundaries'].remove('audit'); r=validate_catalog(c); assert not r.valid; assert any(x.startswith('missing_boundaries:') for x in r.reasons)

def test_cycle_or_future_dependency_rejected():
    c=copy.deepcopy(cat()); c['capabilities'][0]['depends_on']=['cross.domain.qualification']; r=validate_catalog(c); assert not r.valid; assert any('future_dependency' in x or 'dependency_cycle' in x for x in r.reasons)

def test_opening_plan_is_deterministic_and_non_authoritative():
    a=compile_opening_plan(cat()); b=compile_opening_plan(cat()); assert a==b; assert a['implementation_allowed'] is False; assert a['scope']=='phase2-opening-plan-design-only-v1'

def test_catalog_cannot_self_unlock_phase2():
    c=copy.deepcopy(cat()); c['implementation_allowed']=True; r=validate_catalog(c); assert not r.valid; assert 'implementation_must_remain_locked' in r.reasons

def test_capability_risk_and_resource_classes_are_explicit():
    c=cat(); by={x['capability_id']:x for x in c['capabilities']}
    assert by['browser.computer']['risk_class']=='critical'
    assert by['browser.computer']['resource_class']=='browser'
    assert by['gpu.runtime']['resource_class']=='gpu'
    assert by['android.lab']['resource_class']=='device'
