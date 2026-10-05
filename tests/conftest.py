from os import environ
from unittest.mock import MagicMock
from types import SimpleNamespace
from uuid import uuid4

from pytest import fixture

from rtmilk import API, APIAsync, CreateClient, api_async, api_sync

def TaskRsp(*, name='x', tags=None, due='', has_due_time='0', priority='N', url='', notes=None):
	return {'stat': 'ok', 'transaction': {'id': '1', 'undoable': '1'}, 'list': {'id': '10', 'taskseries': [{
		'id': '20', 'created': '2026-10-05T08:00:00Z', 'modified': '2026-10-05T08:00:00Z',
		'name': name, 'source': 'api', 'url': url, 'location_id': '', 'participants': [],
		'notes': notes if notes is not None else [], 'tags': {'tag': tags} if tags else [],
		'task': [{'id': '30', 'added': '2026-10-05T08:00:00Z', 'completed': '', 'deleted': '',
			'due': due, 'estimate': '', 'has_due_time': has_due_time, 'has_start_time': '0',
			'postponed': '0', 'priority': priority, 'start': ''}]}]}}

@fixture
def fakeRtm(monkeypatch):
	fake = SimpleNamespace(calls=[], responses={'rtm.timelines.create': {'stat': 'ok', 'timeline': '1'}})
	def Call(params):
		fake.calls.append(params)
		return fake.responses[params['method']]
	async def CallAsync(params):
		return Call(params)
	monkeypatch.setattr(api_sync, '_CallSync', Call)
	monkeypatch.setattr(api_async, '_CallAsync', CallAsync)
	return fake

try:
	from dotenv import load_dotenv
	load_dotenv()
	print('.env imported')
except ImportError:
	pass

def _GetConfig():
	if 'RTM_TOKEN' in environ:
		return (environ['RTM_API_KEY'], environ['RTM_SHARED_SECRET'], environ['RTM_TOKEN'])
	with open('rtm-token.txt', encoding='utf-8') as f:
		token = f.read()
	return (environ['RTM_API_KEY'], environ['RTM_SHARED_SECRET'], token)

@fixture(scope='session')
def api():
	apiKey, sharedSecret, token = _GetConfig()
	return API(apiKey, sharedSecret, token)

@fixture(scope='session')
def apiAsync():
	apiKey, sharedSecret, token = _GetConfig()
	return APIAsync(apiKey, sharedSecret, token)

@fixture
def timeline(api):
	return api.TimelinesCreate().timeline

@fixture
def task(api, timeline):
	task = api.TasksAdd(timeline, f'new task {uuid4()}')
	yield task
	api.TasksDelete(
		timeline, task.list.id,
		task.list.taskseries[0].id,
		task.list.taskseries[0].task[0].id)

@fixture
def newList(api, timeline):
	list_ = api.ListsAdd(timeline, f'list {uuid4()}')
	yield list_
	list_ = api.ListsDelete(timeline, list_.list.id)
	assert list_.list.deleted is True, list_

@fixture
def newSmartList(api, timeline):
	list_ = api.ListsAdd(timeline, f'list {uuid4()}', filter='tag:tag1')
	yield list_
	list_ = api.ListsDelete(timeline, list_.list.id)
	assert list_.list.deleted is True, list_

class TaskCreator:
	def __init__(self, client_):
		self.client = client_
		self.tasks = []

	def Add(self, name):
		task_ = self.client.Add(name)
		self.tasks.append(task_)
		return task_

	def Cleanup(self):
		for task in self.tasks:
			task.Delete()
		self.tasks.clear()

class TaskCreatorAPI:
	def __init__(self, api, timeline):
		self.api = api
		self.timeline = timeline
		self.tasks = []

	def Add(self, name):
		task = self.api.TasksAdd(self.timeline, name)
		self.tasks.append(task)
		return task

	def Cleanup(self):
		for task in self.tasks:
			self.api.TasksDelete(
				self.timeline, task.list.id,
				task.list.taskseries[0].id,
				task.list.taskseries[0].task[0].id)
		self.tasks.clear()

@fixture
def taskCreatorAPI(api, timeline):
	creator = TaskCreatorAPI(api, timeline)
	yield creator
	creator.Cleanup()

@fixture
def taskCreator(client):
	creator = TaskCreator(client)
	yield creator
	creator.Cleanup()

@fixture
def client():
	apiKey, sharedSecret, token = _GetConfig()
	return CreateClient(apiKey, sharedSecret, token)

@fixture
def mockClient():
	return MagicMock()
