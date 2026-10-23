from pathlib import Path

import pytest

from backend.infrastructure import assets


def test_saved_assets_survive_moving_the_application(monkeypatch, tmp_path):
    previous = tmp_path / 'old' / 'data' / 'assets' / 'asset1' / 'parsed' / 'invoice.pdf'
    monkeypatch.setattr(assets.settings, 'ASSETS', tmp_path / 'old' / 'data' / 'assets')
    original = {'sources': [{'path': str(previous)}]}
    assets.add_storage_references(original)
    source = original['sources'][0]
    assert source['storage_path'] == 'asset1/parsed/invoice.pdf'

    relocated = tmp_path / '新目录 有空格' / 'data' / 'assets'
    monkeypatch.setattr(assets.settings, 'ASSETS', relocated)
    assert assets.asset_file(source) == relocated / 'asset1' / 'parsed' / 'invoice.pdf'
    # Previously saved records need not be rewritten in the shared database.
    assert assets.asset_file({'path': str(previous)}) == assets.asset_file(source)


def test_storage_reference_cannot_escape_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(assets.settings, 'ASSETS', tmp_path / 'data' / 'assets')
    with pytest.raises(ValueError):
        assets.asset_file({'storage_path': '../../outside.txt'})
    with pytest.raises(ValueError):
        assets.asset_file({'path': str(tmp_path / 'unrelated.txt')})
