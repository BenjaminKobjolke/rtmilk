import pytest

from conftest import _GetConfig


def testGetConfigSkipsWithoutCredentials(monkeypatch, tmp_path):
	monkeypatch.delenv('RTM_API_KEY', raising=False)
	monkeypatch.delenv('RTM_SHARED_SECRET', raising=False)
	monkeypatch.delenv('RTM_TOKEN', raising=False)
	monkeypatch.chdir(tmp_path)

	with pytest.raises(pytest.skip.Exception):
		_GetConfig()


def testGetConfigUsesEnvironmentCredentials(monkeypatch):
	monkeypatch.setenv('RTM_API_KEY', 'key')
	monkeypatch.setenv('RTM_SHARED_SECRET', 'secret')
	monkeypatch.setenv('RTM_TOKEN', 'token')

	assert _GetConfig() == ('key', 'secret', 'token')


def testGetConfigUsesTokenFile(monkeypatch, tmp_path):
	monkeypatch.setenv('RTM_API_KEY', 'key')
	monkeypatch.setenv('RTM_SHARED_SECRET', 'secret')
	monkeypatch.delenv('RTM_TOKEN', raising=False)
	monkeypatch.chdir(tmp_path)
	(tmp_path / 'rtm-token.txt').write_text('file-token', encoding='utf-8')

	assert _GetConfig() == ('key', 'secret', 'file-token')
