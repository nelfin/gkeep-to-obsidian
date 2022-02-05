#!/usr/bin/env python

from __future__ import annotations

import argparse
import json
import tarfile
import zipfile
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Optional, Union, Iterator

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
    try:
        n = json.loads(s)
    except json.JSONDecodeError:
        return None
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
    labels = note.labels or []
    return {
        'x-keep-color': note.color,
        'x-keep-archived': note.archived,
        'x-keep-pinned': note.pinned,
        'x-keep-trashed': note.trashed,
        'x-keep-labels': [label['name'] for label in labels],
    }


def keepnote_to_obsidian(n: KeepNote) -> ObsidianNote:
    assert isinstance(n, (ListNote, TextNote))  # FIXME: remove?
    # TODO: tags as folders
    if not n.title:
        slug = n.ctime_us
    else:
        slug = title_to_slug(n.title)
    path = f'{slug}.md'
    metadata = keepnote_metadata(n)
    if isinstance(n, ListNote):
        lines = []
        for item in n.list_content:
            check = 'x' if item['isChecked'] else ' '
            lines.append(f'- [{check}] {item["text"]}')
        content = '\n'.join(lines)
    else:  # isinstance(n, TextNote):
        content = n.text_content
    return ObsidianNote(
        path=path,
        metadata=metadata,
        content=content,
    )


def serialise_metadata(m: dict) -> str:
    # TODO: use PyYAML?
    lines = []
    for k, v in m.items():
        lines.append(f'{k}: {v}')
    return '---\n' + '\n'.join(lines) + '\n---\n'


def obsidiannote_to_markdown(note: ObsidianNote) -> tuple[PathLike, bytes]:
    md = serialise_metadata(note.metadata) + '\n' + note.content + '\n'
    return Path(note.path), md.encode('utf-8')


def archive(p: PathLike) -> Optional[tarfile.TarFile, zipfile.ZipFile]:
    try:
        return zipfile.ZipFile(p)
    except (FileNotFoundError, zipfile.BadZipfile):
        pass
    try:
        return tarfile.open(p)
    except (FileNotFoundError, tarfile.TarError) as ex:
        pass
    return None


def iter_filenames(filespec: str, recursive=True) -> Optional[Iterator[PathLike]]:
    p = Path(filespec)
    if p.is_dir():
        if recursive:
            return p.rglob('*.json')
        else:
            return p.glob('*.json')
    elif p.exists():
        zip = archive(p)
        if zip is not None:
            raise NotImplementedError('need a better interface for temporary extraction')
        return iter([p])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('infile', help=('file(s) to convert: single JSON file, .tgz archive, '
                                        'or extracted directory'),
    )
    parser.add_argument('--destdir', default='out', type=Path,
                        help='destination directory for converted files')
    args = parser.parse_args()

    files = iter_filenames(args.infile)
    if files is None:
        parser.error(f'unable to open {args.infile} for processing')
        # FIXME: optional? instead just raise?
    # TODO: default? files = glob.glob('Takeout/Keep/*.json')

    def iter_notes():
        for fname in files:
            with open(fname, 'r') as f:
                n = parse_note(f.read())
            if n is None:
                continue
            yield obsidiannote_to_markdown(keepnote_to_obsidian(n))

    for path, contents in iter_notes():
        f = args.destdir / path  # type: Path
        f.parent.mkdir(exist_ok=True)
        f.write_bytes(contents)
