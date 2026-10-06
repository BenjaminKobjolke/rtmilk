[![codecov](https://codecov.io/gh/rkhwaja/rtmilk/branch/master/graph/badge.svg?token=RaMYgorajr)](https://codecov.io/gh/rkhwaja/rtmilk) [![PyPI version](https://badge.fury.io/py/rtmilk.svg)](https://badge.fury.io/py/rtmilk)

Python wrapper for "Remember the Milk" [API](https://www.rememberthemilk.com/services/api/)
- Asynchronous and synchronous APIs
- Subscription support

# Usage of client
`CreateClient` creates a timeline on the first write; `CreateClientAsync` creates one up front.

```python
from rtmilk import APIError, CreateClient, CreateClientAsync

# These are the equivalent objects, created differently
client = CreateClient(API_KEY, SHARED_SECRET, TOKEN)
client2 = await CreateClientAsync(API_KEY, SHARED_SECRET, TOKEN)

try:
    task = client.Add(name='name 1')
    assert task.complete.value is False
    task.tags.Set({'tag1', 'tag2'})
    assert task.tags.value == {'tag1', 'tag2'}
    task = await client.AddAsync(name='name 2')
    await task.tags.SetAsync({'tag1', 'tag2'})
    tasks = client2.Get('name:"name 1"')
    assert tasks[0].tags.value == {'tag1', 'tag2'}
except APIError as e:
    print(e)
```

The high-level client also supports list targeting, Smart Add, and common task edits:

```python
from rtmilk import PriorityEnum

task = client.Add('Pick up milk', listId='123', smartAdd=True)
print(task.id)  # listId/taskSeriesId/taskId
task = client.TaskFromId(task.id)  # no fetch; property values start as None
task.priority.Set(PriorityEnum.Priority2)
task.tags.Add({'shopping'})
task.tags.Remove({'old-tag'})
task.dueDate.Set('tomorrow 5pm')
lists = client.GetLists()
tags = client.GetTags()
```

Each sync operation has an async twin, such as `AddAsync`, `GetListsAsync`, and `task.dueDate.SetAsync`.

# Command line

Set `RTM_API_KEY`, `RTM_SHARED_SECRET`, and `RTM_TOKEN` in the environment, then run `rtm <command>`. `rtm auth` needs only the key and shared secret; it opens the authorization URL and prints `RTM_TOKEN=<token>` after authorization. The tool does not read a `.env` file itself.

| Command | Result |
| --- | --- |
| `rtm list [FILTER]` | JSON array of tasks; default filter is `status:incomplete` |
| `rtm lists` / `rtm tags` | JSON array of names |
| `rtm add NAME [--list NAME] [--smart]` | New task |
| `rtm complete ID` / `rtm uncomplete ID` | Completion state |
| `rtm delete ID` | Deletion confirmation |
| `rtm rename ID NAME` | New name |
| `rtm due ID [TEXT]` | Stored due date; omit text to clear |
| `rtm priority ID {1,2,3,N}` | Priority |
| `rtm tag ID [--add TAG ...] [--remove TAG ...]` | Updated tags |
| `rtm note ID TITLE TEXT` | Added note |

Task IDs use `listId/taskSeriesId/taskId`. Successful commands print JSON on stdout, except `auth`, which prints the token line. Errors print JSON on stderr. Exit codes are 0 for success, 1 for API or service errors, and 2 for missing credentials, malformed IDs, or usage errors. Date-only due dates are shown in the machine's local time zone, assumed to match the RTM account time zone.

# Usage of API functions directly
```python
from rtmilk import API, FailStat

api = API(API_KEY, SHARED_SECRET, TOKEN)

timeline = api.TimelinesCreate().timeline
result = api.TasksAdd(timeline, 'task name')
if isinstance(result, FailStat):
    print(f'Error: {result}')
```

```python
from rtmilk import APIAsync, FailStat

apiAsync = APIAsync(API_KEY, SHARED_SECRET, TOKEN)

timeline = await apiAsync.TimelinesCreate().timeline
result = await apiAsync.TasksAdd(timeline, 'task name')
if isinstance(result, FailStat):
    print(f'Error: {result}')
```

# Authorization
```python
from rtmilk import AuthorizationSession

authenticationSession = AuthorizationSession(API_KEY, SHARED_SECRET, 'delete')
input(f'Go to {authenticationSession.url} and authorize. Then Press ENTER')
token = authenticationSession.Done()
print(f'Authorization token is {token}')
```
