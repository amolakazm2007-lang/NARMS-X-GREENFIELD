from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_current_qualifier_emits_current_version_directly_without_report_copy_rewrite():
    current=(ROOT/'scripts/phase1_qualify_current.py').read_text()
    base=(ROOT/'scripts/phase1_qualify_v150.py').read_text()
    assert "VERSION='2.8.0'" in current
    assert 'base.main(version=VERSION)' in current
    assert "old=ROOT/'evidence/phase1-v1.5.0" not in current
    assert "'version':version" in base
    assert "output_dir or f'evidence/phase1-v{version}'" in base
