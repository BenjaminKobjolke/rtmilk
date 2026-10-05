# Copyright (c) 2026 rtmilk contributors
"""JSON command line interface for the high-level RTM client."""

import argparse
import os
import sys
from json import dumps

from . import APIError, AuthorizationSession, BaseError, CreateClient, PriorityEnum


def _Error(message, code=None):
	print(dumps({'error': message, 'code': code}), file=sys.stderr)


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
	commands.add_parser('lists')
	commands.add_parser('tags')
	addParser = commands.add_parser('add')
	addParser.add_argument('name')
	addParser.add_argument('--list')
	addParser.add_argument('--smart', action='store_true')
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


def _ListNames(client):
	return {list_.id: list_.name for list_ in client.GetLists() if not list_.deleted}


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
		listNames = _ListNames(client)
		return [_Row(task, listNames) for task in tasks]
	if args.command == 'lists':
		return list(_ListNames(client).values())
	if args.command == 'tags':
		return client.GetTags()
	if args.command == 'add':
		listNames = _ListNames(client)
		listId = None
		if args.list is not None:
			listId = next((id_ for id_, name in listNames.items() if name.casefold() == args.list.casefold()), None)
			if listId is None:
				raise BaseError(f'List not found: {args.list}')
		task = client.Add(args.name, listId=listId, smartAdd=args.smart)
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
			print(f'Open {session.url} and authorize, then press Enter:', file=sys.stderr)
			input()
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
