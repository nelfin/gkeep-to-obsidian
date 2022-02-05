#!/usr/bin/env python

from __future__ import annotations

import glob
import json
import sys
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Optional, Union

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


KeepNote = Union[ListNote, TextNote]


def _rename_fields(d, mapping):
    for from_, to in mapping:
        if from_ in d:
            d[to] = d[from_]
            del d[from_]
    return d


def parse_note(s) -> Optional[KeepNote]:
    n = json.loads(s)
    n = _rename_fields(n, DEFAULT_NAMES)
    if 'list_content' in n:
        return ListNote(**n)
    elif 'text_content' in n:
        return TextNote(**n)


@dataclass
class ObsidianNote:
    path: str
    metadata: dict
    content: str


def title_to_slug(s: str) -> str:
    # pretty much anything goes
    return s.replace('/', '_')


def keepnote_metadata(note: KeepNote) -> dict:
    return {
        'x-keep-color': note.color,
        'x-keep-archived': note.archived,
        'x-keep-pinned': note.pinned,
        'x-keep-trashed': note.trashed,
        'x-keep-labels': note.labels or [],
    }


def listnote_to_obsidian(note: ListNote) -> ObsidianNote:
    # TODO: tags as folders
    path = f'{title_to_slug(note.title)}.md'
    metadata = keepnote_metadata(note)
    lines = []
    # TODO: list objects?
    for item in note.list_content:
        check = 'x' if item['isChecked'] else ' '
        lines.append(f'- [{check}] {item["text"]}')
    return ObsidianNote(
        path=path,
        metadata=metadata,
        content='\n'.join(lines),
    )


def textnote_to_obsidian(note: TextNote) -> ObsidianNote:
    path = f'{title_to_slug(note.title)}.md'
    metadata = keepnote_metadata(note)
    return ObsidianNote(
        path=path,
        metadata=metadata,
        content=note.text_content,
    )


def serialise_metadata(m: dict) -> str:
    # TODO: use PyYAML?
    lines = []
    for k, v in m.items():
        lines.append(f'{k}: {v}')
    return '---\n' + '\n'.join(lines) + '\n---\n'


def obsidiannote_to_markdown(note: ObsidianNote) -> tuple[PathLike, bytes]:
    md = serialise_metadata(note.metadata) + '\n' + note.content
    return Path(note.path), md.encode('utf-8')


if __name__ == '__main__':
    try:
        files = [sys.argv[1]]
    except IndexError:
        files = glob.glob('Takeout/Keep/*.json')

    def iter_notes():
        for fname in files:
            with open(fname, 'r') as f:
                n = parse_note(f.read())
            if isinstance(n, ListNote):
                onote = listnote_to_obsidian(n)
            elif isinstance(n, TextNote):
                onote = textnote_to_obsidian(n)
            else:
                continue
            yield obsidiannote_to_markdown(onote)

    for path, contents in iter_notes():
        print(path, contents)
