from __future__ import annotations

from datetime import date, datetime, tzinfo
from logging import getLogger
from typing import Generic, TypeVar

from .api_sync import API
from .api_async import APIAsync
from .models import Note, PriorityEnum

_log = getLogger(__name__)
_T = TypeVar('_T')

def _LoadDate(rtmDate, hasTime, tz: tzinfo | None = None):
	if rtmDate is None:
		return None
	# ponytail: Machine time zone assumes the RTM account time zone; use SettingsGetList().settings.timezone with zoneinfo if they differ.
	local = rtmDate.astimezone(tz)
	return local if hasTime else local.date()

def _TagsOf(taskSeries):
	return set(taskSeries.tags.tag) if hasattr(taskSeries.tags, 'tag') else set(taskSeries.tags)

class _Property(Generic[_T]):
	_value: _T | None

	def __init__(self, task):
		self._task = task
		self._value = None

	def __repr__(self):
		return f'{self.__class__.__name__}({self._value})'

	def _LoadValue(self, value: _T):
		self._value = value

	@property
	def value(self) -> _T:
		return self._value # ty: ignore[invalid-return-type]

class NotesProperty(_Property[list[Note]]):

	def Add(self, title: str, text: str):
		self._task._client.api.TasksNotesAdd(
			timeline=self._task._client.timeline,
			list_id=self._task._listId,
			taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId,
			note_title=title,
			note_text=text)

	async def AddAsync(self, title: str, text: str):
		await self._task._client.apiAsync.TasksNotesAdd(
			timeline=self._task._client.timeline,
			list_id=self._task._listId,
			taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId,
			note_title=title,
			note_text=text)

class TagsProperty(_Property[set[str]]):
	def Set(self, value: set[str]):
		task = self._task
		client = task._client
		client.api.TasksSetTags(timeline=self._task._client.timeline,
								list_id=self._task._listId,
								taskseries_id=self._task._taskSeriesId,
								task_id=self._task._taskId,
								tags=list(value))
		self._LoadValue(set(value))

	async def SetAsync(self, value: set[str]):
		task = self._task
		client = task._client
		await client.apiAsync.TasksSetTags(timeline=self._task._client.timeline,
								list_id=self._task._listId,
								taskseries_id=self._task._taskSeriesId,
								task_id=self._task._taskId,
								tags=list(value))
		self._LoadValue(set(value))

	def Add(self, value: set[str]):
		response = self._task._client.api.TasksAddTags(timeline=self._task._client.timeline,
			list_id=self._task._listId, taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId, tags=list(value))
		self._LoadValue(_TagsOf(response.list.taskseries[0]))

	async def AddAsync(self, value: set[str]):
		response = await self._task._client.apiAsync.TasksAddTags(timeline=self._task._client.timeline,
			list_id=self._task._listId, taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId, tags=list(value))
		self._LoadValue(_TagsOf(response.list.taskseries[0]))

	def Remove(self, value: set[str]):
		response = self._task._client.api.TasksRemoveTags(timeline=self._task._client.timeline,
			list_id=self._task._listId, taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId, tags=list(value))
		self._LoadValue(_TagsOf(response.list.taskseries[0]))

	async def RemoveAsync(self, value: set[str]):
		response = await self._task._client.apiAsync.TasksRemoveTags(timeline=self._task._client.timeline,
			list_id=self._task._listId, taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId, tags=list(value))
		self._LoadValue(_TagsOf(response.list.taskseries[0]))

class CompleteProperty(_Property[bool]):
	def Set(self, value: bool):
		if value is True:
			self._task._client.api.TasksComplete(
				timeline=self._task._client.timeline,
				list_id=self._task._listId,
				taskseries_id=self._task._taskSeriesId,
				task_id=self._task._taskId)
		else:
			self._task._client.api.TasksUncomplete(
				timeline=self._task._client.timeline,
				list_id=self._task._listId,
				taskseries_id=self._task._taskSeriesId,
				task_id=self._task._taskId)
		self._LoadValue(value)

	async def SetAsync(self, value: bool):
		if value is True:
			await self._task._client.apiAsync.TasksComplete(
				timeline=self._task._client.timeline,
				list_id=self._task._listId,
				taskseries_id=self._task._taskSeriesId,
				task_id=self._task._taskId)
		else:
			await self._task._client.apiAsync.TasksUncomplete(
				timeline=self._task._client.timeline,
				list_id=self._task._listId,
				taskseries_id=self._task._taskSeriesId,
				task_id=self._task._taskId)
		self._LoadValue(value)

class DateProperty(_Property[date | datetime | None]):
	def __init__(self, task, dateType):
		super().__init__(task)
		self._dateType = dateType

	def _Parameters(self, value):
		parameters = {
			'timeline': self._task._client.timeline,
			'list_id': self._task._listId,
			'taskseries_id': self._task._taskSeriesId,
			'task_id': self._task._taskId,
		}
		if value is not None:
			parameters[self._dateType] = value
			if isinstance(value, str):
				parameters['parse'] = True
			else:
				parameters[f'has_{self._dateType}_time'] = isinstance(value, datetime)
		return parameters

	def Set(self, value: date | datetime | str | None):
		parameters = self._Parameters(value)
		response = (self.__class__.F)(self._task._client.api, **parameters) # ty: ignore[unresolved-attribute]
		task0 = response.list.taskseries[0].task[0]
		self._LoadValue(_LoadDate(getattr(task0, self._dateType), getattr(task0, f'has_{self._dateType}_time')))

	async def SetAsync(self, value: date | datetime | str | None):
		parameters = self._Parameters(value)
		response = await (self.__class__.FA)(self._task._client.apiAsync, **parameters) # ty: ignore[unresolved-attribute]
		task0 = response.list.taskseries[0].task[0]
		self._LoadValue(_LoadDate(getattr(task0, self._dateType), getattr(task0, f'has_{self._dateType}_time')))

class PriorityProperty(_Property[PriorityEnum]):
	def Set(self, value: PriorityEnum):
		self._task._client.api.TasksSetPriority(timeline=self._task._client.timeline,
			list_id=self._task._listId, taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId, priority=value)
		self._LoadValue(value)

	async def SetAsync(self, value: PriorityEnum):
		await self._task._client.apiAsync.TasksSetPriority(timeline=self._task._client.timeline,
			list_id=self._task._listId, taskseries_id=self._task._taskSeriesId,
			task_id=self._task._taskId, priority=value)
		self._LoadValue(value)

class StartDateProperty(DateProperty):
	"""None means no start date"""
	def __init__(self, task):
		super().__init__(task, 'start')
		self.__class__.F = staticmethod(API.TasksSetStartDate) # ty: ignore[unresolved-attribute]
		self.__class__.FA = staticmethod(APIAsync.TasksSetStartDate) # ty: ignore[unresolved-attribute]

class DueDateProperty(DateProperty):
	"""None means no due date"""
	def __init__(self, task):
		super().__init__(task, 'due')
		self.__class__.F = staticmethod(API.TasksSetDueDate) # ty: ignore[unresolved-attribute]
		self.__class__.FA = staticmethod(APIAsync.TasksSetDueDate) # ty: ignore[unresolved-attribute]

class NameProperty(_Property[str]):
	def Set(self, value: str):
		self._task._client.api.TasksSetName(timeline=self._task._client.timeline,
								list_id=self._task._listId,
								taskseries_id=self._task._taskSeriesId,
								task_id=self._task._taskId,
								name=value)
		self._LoadValue(value)

	async def SetAsync(self, value: str):
		await self._task._client.apiAsync.TasksSetName(timeline=self._task._client.timeline,
								list_id=self._task._listId,
								taskseries_id=self._task._taskSeriesId,
								task_id=self._task._taskId,
								name=value)
		self._LoadValue(value)
