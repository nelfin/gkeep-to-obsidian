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
    if 'labels' in n:
        n['labels'] = [label['name'] for label in n['labels']]
    if 'list_content' in n:
        return ListNote(**n)
    elif 'text_content' in n:
        return TextNote(**n)


@dataclass
class ObsidianNote:
    path: PathLike
    metadata: dict
    tags: list[str]
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


def keepnote_to_obsidian(
    n: KeepNote,
    labels_as_folders=True,
    labels_as_tags=False,
    tag_pinned=True,
    archive_dir=None,
    trashed_dir=None,
    **kwargs
) -> ObsidianNote:
    assert isinstance(n, (ListNote, TextNote))  # FIXME: remove?
    if not n.title:
        slug = n.ctime_us
    else:
        slug = title_to_slug(n.title)
    path = Path(f'{slug}.md')
    if labels_as_folders and n.labels:
        path = n.labels[0] / path
    if n.archived and archive_dir:
        path = archive_dir / path
    elif n.trashed and trashed_dir:  # can a note be trashed and archived?
        path = trashed_dir / path
    metadata = keepnote_metadata(n)
    tags = []
    if labels_as_tags and n.labels:
        tags.extend(n.labels)
    if tag_pinned and n.pinned:
        tags.append('pinned')
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
        tags=tags,
        content=content,
    )


def serialise_metadata(m: dict) -> str:
    # TODO: use PyYAML?
    lines = []
    for k, v in m.items():
        lines.append(f'{k}: {v}')
    return '---\n' + '\n'.join(lines) + '\n---\n'


def serialise_tags(tags: list[str]) -> str:
    return '\n'.join('#'+tag for tag in tags)


def obsidiannote_to_markdown(
    note: ObsidianNote,
    add_metadata=True,
    **kwargs
) -> tuple[PathLike, bytes]:
    if add_metadata:
        md = serialise_metadata(note.metadata) + '\n'
    else:
        md = ''
    md += note.content + '\n'
    if note.tags:
        md += '\n' + serialise_tags(note.tags) + '\n'
    return note.path, md.encode('utf-8')


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
    parser.add_argument('--archived', action='store_true', help='convert archived notes')
    parser.add_argument('--archive-dir', dest='archive_dir', default='Archived',
                        help='subdirectory for archived notes')
    parser.add_argument('--trashed', action='store_true', help='convert trashed notes')
    parser.add_argument('--trashed-dir', dest='trashed_dir', default='Trashed',
                        help='subdirectory for trashed notes')
    parser.add_argument('--no-metadata', action='store_false', dest='add_metadata')
    parser.add_argument('--labels-as-tags', action='store_true', dest='labels_as_tags')
    parser.add_argument('--no-labels-as-folders', action='store_false', dest='labels_as_folders')
    parser.add_argument('--no-tag-pinned', action='store_false', dest='tag_pinned')
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
            if n.archived and not args.archived:
                continue
            if n.trashed and not args.trashed:
                continue
            o_note = keepnote_to_obsidian(n, **vars(args))
            yield obsidiannote_to_markdown(o_note, **vars(args))

    for path, contents in iter_notes():
        f = args.destdir / path  # type: Path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(contents)
