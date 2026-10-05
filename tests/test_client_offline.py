# Copyright (c) 2026 rtmilk contributors
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import TaskRsp
from rtmilk import APIError, CreateClient, CreateClientAsync, PriorityEnum
from rtmilk._properties import _LoadDate

INVALID_TASK_CODE = 340

def _Responses(fakeRtm):
	fakeRtm.responses.update({
		'rtm.tasks.add': TaskRsp(), 'rtm.tasks.getList': {'stat': 'ok', 'tasks': {'rev': '1', 'list': [{'id': '10', 'taskseries': TaskRsp()['list']['taskseries']}]}},
		'rtm.tasks.setPriority': TaskRsp()['list'], 'rtm.tasks.addTags': TaskRsp(tags=['a']),
		'rtm.tasks.removeTags': TaskRsp(), 'rtm.tasks.setDueDate': TaskRsp(due='2026-10-06T15:00:00Z', has_due_time='1'),
		'rtm.lists.getList': {'stat': 'ok', 'lists': {'list': [{'id': '10', 'name': 'Inbox', 'deleted': '0', 'locked': '0', 'archived': '0', 'position': '0', 'smart': '0'}]}},
		'rtm.tags.getList': {'stat': 'ok', 'tags': {'tag': [{'name': 'a'}]}},
	})


def test_client_operations(fakeRtm):
	_Responses(fakeRtm)
	client = CreateClient('k', 's', 't')
	task = client.Add('x')
	assert task.id == '10/20/30'
	assert task.listId == '10'
	assert 'list_id' not in fakeRtm.calls[-1]
	assert 'parse' not in fakeRtm.calls[-1]
	client.Add('x', listId='7', smartAdd=True)
	assert fakeRtm.calls[-1]['list_id'] == '7'
	assert fakeRtm.calls[-1]['parse'] == '1'
	assert client.TaskFromId(task.id).id == task.id
	for id_ in ('10/20', '10//30', ''):
		with pytest.raises(ValueError, match='Malformed task id'):
			client.TaskFromId(id_)
	loaded = client.Get('status:incomplete')[0]
	assert loaded.priority.value == PriorityEnum.NoPriority
	assert loaded.url is None
	task.priority.Set(PriorityEnum.Priority2)
	assert fakeRtm.calls[-1]['method'] == 'rtm.tasks.setPriority'
	assert fakeRtm.calls[-1]['priority'] == '2'
	assert task.priority.value == PriorityEnum.Priority2
	fakeRtm.responses['rtm.tasks.setPriority'] = {'stat': 'fail', 'err': {'code': '340', 'msg': 'task_id invalid or not provided'}}
	with pytest.raises(APIError) as error:
		task.priority.Set(PriorityEnum.Priority2)
	assert error.value.code == INVALID_TASK_CODE
	task.tags.Add({'a'})
	assert fakeRtm.calls[-1]['method'] == 'rtm.tasks.addTags'
	assert fakeRtm.calls[-1]['tags'] == 'a'
	assert task.tags.value == {'a'}
	task.tags.Remove({'a'})
	assert fakeRtm.calls[-1]['method'] == 'rtm.tasks.removeTags'
	assert task.tags.value == set()
	task.dueDate.Set('tomorrow 5pm')
	assert fakeRtm.calls[-1]['due'] == 'tomorrow 5pm'
	assert fakeRtm.calls[-1]['parse'] == '1'
	assert 'has_due_time' not in fakeRtm.calls[-1]
	assert isinstance(task.dueDate.value, datetime)
	task.dueDate.Set(None)
	assert 'due' not in fakeRtm.calls[-1]
	task.dueDate.Set(date(2026, 10, 6))
	assert fakeRtm.calls[-1]['has_due_time'] == '0'
	assert client.GetLists()[0].name == 'Inbox'
	assert client.GetTags() == ['a']


def test_date_only_uses_local_day():
	instant = datetime(2026, 10, 5, 22, tzinfo=timezone.utc)
	localZone = timezone(timedelta(hours=2))
	assert _LoadDate(instant, False, tz=localZone) == date(2026, 10, 6)
	assert _LoadDate(instant, True, tz=localZone).utcoffset() == timedelta(hours=2)
	assert _LoadDate(instant, True, tz=localZone) == instant


@pytest.mark.asyncio
async def test_async_client_operations(fakeRtm):
	_Responses(fakeRtm)
	client = await CreateClientAsync('k', 's', 't')
	task = await client.AddAsync('x', listId='7', smartAdd=True)
	assert fakeRtm.calls[-1]['list_id'] == '7'
	assert fakeRtm.calls[-1]['parse'] == '1'
	await task.priority.SetAsync(PriorityEnum.Priority2)
	await task.tags.AddAsync({'a'})
	await task.dueDate.SetAsync('tomorrow')
	assert task.priority.value == PriorityEnum.Priority2
	assert task.tags.value == {'a'}
	assert isinstance(task.dueDate.value, datetime)
	assert (await client.GetListsAsync())[0].name == 'Inbox'
	assert await client.GetTagsAsync() == ['a']
