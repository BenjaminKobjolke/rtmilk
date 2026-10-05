# Copyright (c) 2026 rtmilk contributors
from json import loads

import pytest

from conftest import TaskRsp
from rtmilk import cli

USAGE_ERROR = 2

@pytest.fixture
def cliRtm(fakeRtm, monkeypatch):
	for name in ('RTM_API_KEY', 'RTM_SHARED_SECRET', 'RTM_TOKEN'):
		monkeypatch.setenv(name, name)
	fakeRtm.responses.update({
		'rtm.lists.getList': {'stat': 'ok', 'lists': {'list': [
			{'id': '10', 'name': 'Inbox', 'deleted': '0', 'locked': '0', 'archived': '0', 'position': '0', 'smart': '0'},
			{'id': '11', 'name': 'Old', 'deleted': '1', 'locked': '0', 'archived': '0', 'position': '1', 'smart': '0'}]}},
		'rtm.tags.getList': {'stat': 'ok', 'tags': {'tag': [{'name': 'a'}]}},
		'rtm.tasks.getList': {'stat': 'ok', 'tasks': {'rev': '1', 'list': [{'id': '10', 'taskseries': TaskRsp()['list']['taskseries']}]}},
		'rtm.tasks.add': TaskRsp(), 'rtm.tasks.complete': TaskRsp(), 'rtm.tasks.uncomplete': TaskRsp(),
		'rtm.tasks.delete': TaskRsp(), 'rtm.tasks.setName': TaskRsp(name='new'),
		'rtm.tasks.setDueDate': TaskRsp(due='2026-10-06T15:00:00Z', has_due_time='1'),
		'rtm.tasks.setPriority': TaskRsp()['list'], 'rtm.tasks.addTags': TaskRsp(tags=['a']),
		'rtm.tasks.removeTags': TaskRsp(),
		'rtm.tasks.notes.add': {'stat': 'ok', 'transaction': {'id': '1', 'undoable': '1'}, 'note': {
			'id': '1', 'created': '2026-10-05T08:00:00Z', 'modified': '2026-10-05T08:00:00Z', 'title': 't', '$t': 'body'}},
	})
	return fakeRtm


def _Output(capsys):
	return loads(capsys.readouterr().out)


def test_missing_token(cliRtm, monkeypatch, capsys):  # noqa: ARG001 - fixture supplies the fake API
	monkeypatch.delenv('RTM_TOKEN')
	assert cli.Main(['lists']) == USAGE_ERROR
	assert loads(capsys.readouterr().err) == {'error': 'Missing environment variable: RTM_TOKEN', 'code': None}


def test_list_and_names(cliRtm, capsys):
	assert cli.Main(['list']) == 0
	row = _Output(capsys)[0]
	assert set(row) == {'id', 'name', 'list', 'due', 'priority', 'tags', 'completed', 'url', 'notes'}
	assert row['list'] == 'Inbox'
	assert row['id'] == '10/20/30'
	assert next(call for call in cliRtm.calls if call['method'] == 'rtm.tasks.getList')['filter'] == 'status:incomplete'
	assert cli.Main(['lists']) == 0
	assert _Output(capsys) == ['Inbox']
	assert cli.Main(['tags']) == 0
	assert _Output(capsys) == ['a']


def test_add_list_selection(cliRtm, capsys):
	assert cli.Main(['add', 'x', '--list', 'inbox', '--smart']) == 0
	assert _Output(capsys)['list'] == 'Inbox'
	call = cliRtm.calls[-1]
	assert call['method'] == 'rtm.tasks.add'
	assert call['list_id'] == '10'
	assert call['parse'] == '1'
	for name in ('unknown', 'Old'):
		before = len([call for call in cliRtm.calls if call['method'] == 'rtm.tasks.add'])
		assert cli.Main(['add', 'x', '--list', name]) == 1
		assert loads(capsys.readouterr().err)['code'] is None
		assert len([call for call in cliRtm.calls if call['method'] == 'rtm.tasks.add']) == before


@pytest.mark.parametrize(('arguments', 'method', 'expected'), [
	(['complete', '10/20/30'], 'rtm.tasks.complete', {'id': '10/20/30', 'completed': True}),
	(['uncomplete', '10/20/30'], 'rtm.tasks.uncomplete', {'id': '10/20/30', 'completed': False}),
	(['delete', '10/20/30'], 'rtm.tasks.delete', {'id': '10/20/30', 'deleted': True}),
	(['rename', '10/20/30', 'new'], 'rtm.tasks.setName', {'id': '10/20/30', 'name': 'new'}),
	(['due', '10/20/30', 'tomorrow'], 'rtm.tasks.setDueDate', None),
	(['due', '10/20/30'], 'rtm.tasks.setDueDate', None),
	(['priority', '10/20/30', '2'], 'rtm.tasks.setPriority', {'id': '10/20/30', 'priority': '2'}),
	(['tag', '10/20/30', '--add', 'a'], 'rtm.tasks.addTags', {'id': '10/20/30', 'tags': ['a']}),
	(['tag', '10/20/30', '--remove', 'a'], 'rtm.tasks.removeTags', {'id': '10/20/30', 'tags': []}),
	(['note', '10/20/30', 't', 'body'], 'rtm.tasks.notes.add', {'id': '10/20/30', 'note': {'title': 't', 'text': 'body'}}),
])
def test_mutations(cliRtm, capsys, arguments, method, expected):
	assert cli.Main(arguments) == 0
	result = _Output(capsys)
	if expected is not None:
		assert result == expected
	else:
		assert result['id'] == '10/20/30'
		assert result['due'] is not None
	call = cliRtm.calls[-1]
	assert call['method'] == method
	for key, value in {'list_id': '10', 'taskseries_id': '20', 'task_id': '30'}.items():
		assert call[key] == value


def test_usage_and_api_error(cliRtm, capsys):
	assert cli.Main(['complete', '10/20']) == USAGE_ERROR
	assert loads(capsys.readouterr().err)['code'] is None
	assert len(cliRtm.calls) == 1
	assert cli.Main(['tag', '10/20/30']) == USAGE_ERROR
	assert loads(capsys.readouterr().err)['code'] is None
	cliRtm.responses['rtm.tasks.setPriority'] = {'stat': 'fail', 'err': {'code': '340', 'msg': 'bad task'}}
	assert cli.Main(['priority', '10/20/30', '1']) == 1
	assert loads(capsys.readouterr().err) == {'error': 'bad task', 'code': 340}


def test_auth(monkeypatch, capsys):
	monkeypatch.setenv('RTM_API_KEY', 'k')
	monkeypatch.setenv('RTM_SHARED_SECRET', 's')
	monkeypatch.delenv('RTM_TOKEN', raising=False)
	class Session:
		def __init__(self, key, secret, perms):
			assert (key, secret, perms) == ('k', 's', 'delete')
			self.url = 'https://example.test/auth'
		def Done(self):
			return 'tok'
	monkeypatch.setattr(cli, 'AuthorizationSession', Session)
	answers = iter(['o', ''])
	opened = []
	monkeypatch.setattr('builtins.input', lambda: next(answers))
	monkeypatch.setattr(cli.webbrowser, 'open', opened.append)
	assert cli.Main(['auth']) == 0
	output = capsys.readouterr()
	assert output.out.strip() == 'RTM_TOKEN=tok'
	assert 'https://example.test/auth' in output.err
	assert opened == ['https://example.test/auth']
