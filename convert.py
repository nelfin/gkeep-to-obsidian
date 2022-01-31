#!/usr/bin/env python
import glob
import json
from dataclasses import dataclass
from typing import Optional

DEFAULT_NAMES = [
    ('textContent', 'text_content'),
    ('listContent', 'list_content'),
    ('isTrashed', 'trashed'),
    ('isPinned', 'pinned'),
    ('isArchived', 'archived'),
    ('userEditedTimestampUsec', 'mtime_us'),
    ('createdTimestampUsec', 'ctime_us'),
]


@dataclass
class Note:
    title: str
    color: str
    mtime_us: int  # TODO: us -> s/ns?
    ctime_us: int
    # TODO: should these be types?
    archived: bool
    pinned: bool
    trashed: bool

# @dataclass
# class NoteOptions:
#     labels: Optional[list] = None
#     annotations: Optional[list] = None
#     attachments: Optional[list] = None

@dataclass
class ListNote(Note):
    list_content: list
    labels: Optional[list] = None
    annotations: Optional[list] = None
    attachments: Optional[list] = None

@dataclass
class TextNote(Note):
    text_content: str
    labels: Optional[list] = None
    annotations: Optional[list] = None
    attachments: Optional[list] = None


def _rename_fields(d, mapping):
    for from_, to in mapping:
        if from_ in d:
            d[to] = d[from_]
            del d[from_]
    return d


def parse_note(s):
    n = json.loads(s)
    n = _rename_fields(n, DEFAULT_NAMES)
    if 'list_content' in n:
        return ListNote(**n)
    elif 'text_content' in n:
        return TextNote(**n)


for fname in glob.glob('Takeout/Keep/*.json'):
    with open(fname, 'r') as f:
        try:
            n = parse_note(f.read())
        except TypeError as ex:
            n = str(ex)
        print(fname, n)
