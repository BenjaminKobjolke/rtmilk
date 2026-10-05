from __future__ import annotations

from datetime import datetime
from logging import getLogger

from pydantic import validate_call

from .api_async import APIAsync
from .api_sync import API
from .models import RTMList, _RaiseIfError
from ._properties import CompleteProperty, DueDateProperty, NameProperty, NotesProperty, PriorityProperty, StartDateProperty, TagsProperty, _LoadDate, _TagsOf

_log = getLogger(__name__)
_TASK_ID_PARTS = 3

class Task:
	"""Represents an RTM task"""

	def __init__(self, client, listId, taskSeriesId, taskId):
		self._client = client
		self._listId = listId
		self._taskSeriesId = taskSeriesId
		self._taskId = taskId

		self.name = NameProperty(self)
		self.tags = TagsProperty(self)
		self.startDate = StartDateProperty(self)
		self.dueDate = DueDateProperty(self)
		self.complete = CompleteProperty(self)
		self.notes = NotesProperty(self)
		self.priority = PriorityProperty(self)
		self.url: str | None = None
		self.createTime: datetime | None = None
		self.modifiedTime: datetime | None = None

	def __repr__(self):
		return f'Task({self.name.value})'

	@property
	def id(self) -> str:
		return f'{self._listId}/{self._taskSeriesId}/{self._taskId}'

	@property
	def listId(self) -> str:
		return self._listId

	@validate_call
	def Delete(self):
		_log.info(f'{self}.Delete')
		_RaiseIfError(self._client.api.TasksDelete(timeline=self._client.timeline,
								list_id=self._listId,
								taskseries_id=self._taskSeriesId,
								task_id=self._taskId))

	@validate_call
	async def DeleteAsync(self):
		_log.info(f'{self}.DeleteAsync')
		_RaiseIfError(await self._client.apiAsync.TasksDelete(timeline=self._client.timeline,
								list_id=self._listId,
								taskseries_id=self._taskSeriesId,
								task_id=self._taskId))

# Serialize python datetime object to string for use by filters
def FilterDate(date_):
	return datetime.strftime(date_, '%m/%d/%Y')

def _CreateFromTaskSeries(client, listId, taskSeries):
	_log.info(f'{taskSeries=}')
	task0 = taskSeries.task[0]
	result = Task(client, listId, taskSeries.id, task0.id)

	result.name._LoadValue(taskSeries.name)
	result.tags._LoadValue(_TagsOf(taskSeries))
	result.startDate._LoadValue(_LoadDate(task0.start, task0.has_start_time))
	result.dueDate._LoadValue(_LoadDate(task0.due, task0.has_due_time))
	result.complete._LoadValue(task0.completed is not None)
	result.priority._LoadValue(task0.priority)
	result.notes._LoadValue([] if isinstance(taskSeries.notes, list) else taskSeries.notes.note)
	result.url = taskSeries.url
	result.createTime = taskSeries.created
	result.modifiedTime = taskSeries.modified

	return result

def _CreateListOfTasks(client, listResponse):
	if listResponse.tasks.list is None:
		return []
	tasks = []
	for list_ in listResponse.tasks.list:
		if not hasattr(list_, 'taskseries') or list_.taskseries is None:
			continue
		tasks.extend([_CreateFromTaskSeries(client, listId=list_.id, taskSeries=ts) for ts in list_.taskseries])
	return tasks

def CreateClient(clientId: str, clientSecret: str, token: str) -> _Client:
	"""Create RTM client object synchronously"""
	client = _Client(clientId, clientSecret, token)
	client._CreateTimeline()
	return client

async def CreateClientAsync(clientId: str, clientSecret: str, token: str) -> _Client:
	"""Create RTM client object asynchronously"""
	client = _Client(clientId, clientSecret, token)
	await client._CreateTimelineAsync()
	return client

class _Client:
	"""Wraps the timeline and adds convenience functions to add and query tasks"""

	def __init__(self, clientId: str, clientSecret: str, token: str):
		self.api = API(clientId, clientSecret, token)
		self.apiAsync = APIAsync(clientId, clientSecret, token)
		self.timeline = None

	def __repr__(self):
		return '_Client()'

	def _CreateTimeline(self):
		self.timeline = _RaiseIfError(self.api.TimelinesCreate().timeline)

	async def _CreateTimelineAsync(self):
		self.timeline = _RaiseIfError((await self.apiAsync.TimelinesCreate()).timeline)

	@validate_call
	def Get(self, filter_: str, lastSync: datetime | None = None) -> list[Task]:
		_log.info(f'Get: {filter_}, {lastSync}')
		listResponse = _RaiseIfError(self.api.TasksGetList(filter=filter_, last_sync=lastSync))
		return _CreateListOfTasks(self, listResponse)

	@validate_call
	def Add(self, name: str, listId: str | None = None, smartAdd: bool = False) -> Task:
		_log.info(f'Add: {name}')
		taskResponse = _RaiseIfError(self.api.TasksAdd(self.timeline, name, list_id=listId, parse=True if smartAdd else None)) # ty: ignore[invalid-argument-type]
		return _CreateFromTaskSeries(self, listId=taskResponse.list.id, taskSeries=taskResponse.list.taskseries[0])

	@validate_call
	async def GetAsync(self, filter_: str, lastSync: datetime | None = None) -> list[Task]:
		_log.info(f'GetAsync: {filter_}, {lastSync}')
		listResponse = _RaiseIfError(await self.apiAsync.TasksGetList(filter=filter_, last_sync=lastSync))
		return _CreateListOfTasks(self, listResponse)

	@validate_call
	async def AddAsync(self, name: str, listId: str | None = None, smartAdd: bool = False) -> Task:
		_log.info(f'AddAsync: {name}')
		taskResponse = _RaiseIfError(await self.apiAsync.TasksAdd(self.timeline, name, list_id=listId, parse=True if smartAdd else None)) # ty: ignore[invalid-argument-type]
		return _CreateFromTaskSeries(self, listId=taskResponse.list.id, taskSeries=taskResponse.list.taskseries[0])

	@validate_call
	def GetLists(self) -> list[RTMList]:
		return _RaiseIfError(self.api.ListsGetList()).lists.list

	@validate_call
	async def GetListsAsync(self) -> list[RTMList]:
		return _RaiseIfError(await self.apiAsync.ListsGetList()).lists.list

	@validate_call
	def GetTags(self) -> list[str]:
		return [tag.name for tag in _RaiseIfError(self.api.TagsGetList()).tags.tag]

	@validate_call
	async def GetTagsAsync(self) -> list[str]:
		return [tag.name for tag in _RaiseIfError(await self.apiAsync.TagsGetList()).tags.tag]

	@validate_call
	def TaskFromId(self, id_: str) -> Task:
		"""Build a task by id without fetching it; property values stay None until a setter runs."""
		parts = id_.split('/')
		if len(parts) != _TASK_ID_PARTS or not all(parts):
			raise ValueError(f'Malformed task id: {id_}')
		return Task(self, *parts)
