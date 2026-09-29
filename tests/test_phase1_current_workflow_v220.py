from pathlib import Path

def test_workflow_uses_current_versioned_scripts_and_paths():
    root=Path(__file__).resolve().parents[1]
    text=(root/'.github/workflows/phase1-closure.yml').read_text()
    assert 'phase1_qualify_current.py' in text
    assert 'build_phase1_attestation_current.py' in text
    assert 'phase1-v2.8.0/qualification-report.json' in text
    assert 'phase1-v2.8.0/closure-attestation.json' in text
    assert 'phase1-closure.yml@v2.8.0' in text
    assert 'phase1-v1.8.0' not in text
