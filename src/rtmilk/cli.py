# Copyright (c) 2026 rtmilk contributors
"""JSON command line interface for the high-level RTM client."""

import argparse
import os
import sys
import webbrowser
from contextlib import suppress
from hashlib import sha256
from json import dump, dumps, load
from time import time

from . import APIError, AuthorizationSession, BaseError, CreateClient, PriorityEnum


def _Error(message, code=None):
	print(dumps({'error': message, 'code': code}), file=sys.stderr)


_CACHE_DIR = os.path.join(os.path.expanduser('~'), '.cache', 'rtmilk')
_CACHE_SECONDS = 3600


def _CachePath(kind):
	account = sha256(f"{os.environ['RTM_API_KEY']}:{os.environ['RTM_TOKEN']}".encode()).hexdigest()[:16]
	return os.path.join(_CACHE_DIR, f'{account}-{kind}.json')


def _ReadCache(kind):
	"""Return a valid fresh cache entry, or None."""
	path = _CachePath(kind)
	try:
		if not 0 <= time() - os.path.getmtime(path) < _CACHE_SECONDS:
			return None
		with open(path, encoding='utf-8') as file:
			value = load(file)
	except (OSError, ValueError):
		return None
	if kind == 'lists' and isinstance(value, dict) and all(isinstance(key, str) and isinstance(name, str) for key, name in value.items()):
		return value
	if kind == 'tags' and isinstance(value, list) and all(isinstance(tag, str) for tag in value):
		return value
	return None


def _WriteCache(kind, value):
	path = _CachePath(kind)
	temporary = f'{path}.{os.getpid()}.tmp'
	with suppress(OSError):
		os.makedirs(_CACHE_DIR, exist_ok=True)
		with open(temporary, 'w', encoding='utf-8') as file:
			dump(value, file)
		os.replace(temporary, path)


class _Parser(argparse.ArgumentParser):
	def error(self, message):
		_Error(message)
		raise SystemExit(2)


def _BuildParser():
	parser = _Parser(prog='rtm')
	commands = parser.add_subparsers(dest='command', required=True, parser_class=_Parser)
	commands.add_parser('auth')
	listParser = commands.add_parser('list')
	listParser.add_argument('filter', nargs='?', default='status:incomplete')
	for command in ('lists', 'tags'):
		commands.add_parser(command).add_argument('--refresh', action='store_true')
	listParser.add_argument('--refresh', action='store_true')
	addParser = commands.add_parser('add')
	addParser.add_argument('name')
	addParser.add_argument('--list')
	addParser.add_argument('--smart', action='store_true')
	addParser.add_argument('--refresh', action='store_true')
	for command in ('complete', 'uncomplete', 'delete', 'rename', 'due', 'priority', 'tag', 'note'):
		commandParser = commands.add_parser(command)
		commandParser.add_argument('id')
		if command == 'rename':
			commandParser.add_argument('name')
		elif command == 'due':
			commandParser.add_argument('text', nargs='?')
		elif command == 'priority':
			commandParser.add_argument('priority', choices=('1', '2', '3', 'N'))
		elif command == 'tag':
			commandParser.add_argument('--add', action='append', default=[])
			commandParser.add_argument('--remove', action='append', default=[])
		elif command == 'note':
			commandParser.add_argument('title')
			commandParser.add_argument('text')
	return parser


def _ListNames(client, refresh=False, complete=lambda _: True):
	# ponytail: a list id absent from every lists response triggers one refetch per command; revisit if observed.
	names = None if refresh else _ReadCache('lists')
	if names is None or not complete(names):
		names = {list_.id: list_.name for list_ in client.GetLists() if not list_.deleted}
		_WriteCache('lists', names)
	return names


def _Tags(client, refresh=False):
	tags = None if refresh else _ReadCache('tags')
	if tags is None:
		tags = client.GetTags()
		_WriteCache('tags', tags)
	return tags


def _ForgetTagsUnlessKnown(tags):
	cached = _ReadCache('tags')
	if cached is not None and not set(tags) <= set(cached):
		with suppress(OSError):
			os.remove(_CachePath('tags'))


def _FindList(listNames, name):
	return next((id_ for id_, listName in listNames.items() if listName.casefold() == name.casefold()), None)


def _Row(task, listNames):
	return {
		'id': task.id,
		'name': task.name.value,
		'list': listNames.get(task.listId, task.listId),
		'due': task.dueDate.value.isoformat() if task.dueDate.value is not None else None,
		'priority': task.priority.value.value,
		'tags': sorted(task.tags.value),
		'completed': task.complete.value,
		'url': task.url,
		'notes': [{'title': note.title, 'body': note.body} for note in task.notes.value],
	}


def _Run(client, args):  # noqa: C901, PLR0911, PLR0912 - command dispatch mirrors the CLI contract
	if args.command == 'list':
		tasks = client.Get(args.filter)
		listNames = _ListNames(client, args.refresh, lambda names: all(task.listId in names for task in tasks))
		_ForgetTagsUnlessKnown(tag for task in tasks for tag in task.tags.value)
		return [_Row(task, listNames) for task in tasks]
	if args.command == 'lists':
		return list(_ListNames(client, args.refresh).values())
	if args.command == 'tags':
		return _Tags(client, args.refresh)
	if args.command == 'add':
		listNames = _ListNames(client, args.refresh, lambda names: args.list is None or _FindList(names, args.list) is not None)
		listId = None
		if args.list is not None:
			listId = _FindList(listNames, args.list)
			if listId is None:
				raise BaseError(f'List not found: {args.list}')
		task = client.Add(args.name, listId=listId, smartAdd=args.smart)
		if task.listId not in listNames:
			listNames = _ListNames(client, refresh=True)
		_ForgetTagsUnlessKnown(task.tags.value)
		return _Row(task, listNames)
	if args.command == 'tag' and not (args.add or args.remove):
		raise ValueError('tag requires --add or --remove')
	task = client.TaskFromId(args.id)
	if args.command in ('complete', 'uncomplete'):
		value = args.command == 'complete'
		task.complete.Set(value)
		return {'id': task.id, 'completed': task.complete.value}
	if args.command == 'delete':
		task.Delete()
		return {'id': task.id, 'deleted': True}
	if args.command == 'rename':
		task.name.Set(args.name)
		return {'id': task.id, 'name': task.name.value}
	if args.command == 'due':
		task.dueDate.Set(args.text)
		return {'id': task.id, 'due': task.dueDate.value.isoformat() if task.dueDate.value is not None else None}
	if args.command == 'priority':
		task.priority.Set(PriorityEnum(args.priority))
		return {'id': task.id, 'priority': task.priority.value.value}
	if args.command == 'tag':
		if args.add:
			task.tags.Add(set(args.add))
		if args.remove:
			task.tags.Remove(set(args.remove))
		_ForgetTagsUnlessKnown(task.tags.value)
		return {'id': task.id, 'tags': sorted(task.tags.value)}
	if args.command == 'note':
		task.notes.Add(args.title, args.text)
		return {'id': task.id, 'note': {'title': args.title, 'text': args.text}}
	raise RuntimeError(f'Unknown command: {args.command}')


def Main(argv=None) -> int:
	parser = _BuildParser()
	args = parser.parse_args(argv)
	for name in ('RTM_API_KEY', 'RTM_SHARED_SECRET', *(() if args.command == 'auth' else ('RTM_TOKEN',))):
		if not os.environ.get(name):
			_Error(f'Missing environment variable: {name}')
			return 2
	try:
		if args.command == 'auth':
			session = AuthorizationSession(os.environ['RTM_API_KEY'], os.environ['RTM_SHARED_SECRET'], 'delete')
			print(f'Open {session.url} and authorize, then press Enter (type o + Enter to open it in the default browser):', file=sys.stderr)
			while input().strip().lower() == 'o':
				webbrowser.open(session.url)
			print(f'RTM_TOKEN={session.Done()}')
		else:
			client = CreateClient(os.environ['RTM_API_KEY'], os.environ['RTM_SHARED_SECRET'], os.environ['RTM_TOKEN'])
			result = _Run(client, args)
			print(dumps(result))
	except APIError as error:
		_Error(error.message, error.code)
		return 1
	except ValueError as error:
		_Error(str(error))
		return 2
	except BaseError as error:
		_Error(str(error))
		return 1
	return 0
