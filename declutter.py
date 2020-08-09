#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
DeclutterPY

This module assists in the organization of files and directories. When run as a
script, it accepts a list of filepaths as arguments.

To start the program prompts you for a series of single-character shortcuts
followed by directories until an empty line is given, eg:

  $ Enter a shortcut and path (empty line when done): p ~/Pictures
  $ Enter a shortcut and path (empty line when done): h ~/
  $ Enter a shortcut and path (empty line when done):

Each file is then moved to a new location using one of the defined shortcuts.

Once files are moved using Organizer, their new location is stored in a config
file. This allows you to periodically organize directories while skipping
previously organized files. The -H option disables loading or saving of history.

Shortcuts are also saved for future use. The -S option disables loading or
saving of shortcuts. Both filepath and shortcut history can both be disabled
simultaneously with -i

Other Keys
-Left:  Go back to the previous file (eg, to change its location)
-Right: Skip the current file without saving it to history
-Down:  Keep the file in its current location, saving it to history
-Up:    Pause organizing to add new shortcuts
-?:     Show shortcuts and commands
"""

from __future__ import annotations

import os
import _io
import sys
import json
import shutil
import logging
import readline
from glob import glob
from pathlib import Path
from types import TracebackType
from typing import Union, Tuple, Dict, Optional, List, Iterable, Callable, Set, Iterator

try:
    from .exceptions import ReservedShortcutException, InputFormatException
    from .exceptions import EmptyInputException, InvalidKeyException
    from .exceptions import InvalidShortcutException, SimpleException
except:
    from exceptions import ReservedShortcutException, InputFormatException
    from exceptions import EmptyInputException, InvalidKeyException
    from exceptions import InvalidShortcutException, SimpleException

__version__ = '0.1'

# TODO - Ensure good type hint coverage
# TODO - Add docstrings (Google format)
# TODO - Remove logging
logging.basicConfig(filename=Path.home().joinpath('.declutterpy.log'), level=logging.DEBUG)

class Shortcut:
    _key: str
    _path: Path

    def __init__(self, key: str, path: Union[str, Path]):
        self.key = key
        self.path = Path(path)

    def __str__(self):
        return f"{self._key}: {self.path}"

    def __eq__(self, o):
        return self.key == o.key

    @property
    def key(self) -> str:
        return self._key

    @key.setter
    def key(self, key: str) -> None:
        # Can only be one character
        if len(key) != 1:
            raise InvalidKeyException(f"'{key}' is not length 1")

        self._key = key

    @property
    def path(self) -> Path:
        return self._path
    
    @path.setter
    def path(self, path: Union[str, Path]) -> None:
        _path: Path = Path(path)

        # Path must be an existing directory with write permission
        if not _path.is_dir():
            raise NotADirectoryError(_path)
        if not os.access(_path, os.W_OK):
            raise PermissionError(f"Cannot write to {_path}")

        self._path = _path

    def as_dict(self) -> Dict[str, Path]:
        return {self._key: self._path}

class OrganizedFile(type(Path())): # type: ignore
    """
    Subclass of pathlib.Path that tracks whether or not a file has been
    organized and is at its desired location.
    """
    _is_organized: bool

    def __init__(self, path: Union[str, Path], is_organized: bool = False):
        self._is_organized = is_organized

    @property
    def path(self):
        return self.absolute().__str__()

    @property
    def organized(self):
        return self._is_organized

    @organized.setter
    def organized(self, is_organized: bool):
        self._is_organized = is_organized

    def iterdir(self, depth: int = 0, recursive: bool = False) -> Iterable[OrganizedFile]:
        """
        Iterate over the files in this directory. Does not yield any
        result for the special paths '.' and '..'. Allows for recursively
        descending into the directory infinitely or up to a specified depth.

        If recursive is specified but not depth (or depth == 0), iterdir()
        will descend into all subdirectories.

        If recursive is True and depth is specified to be anything other than 0,
        then iterdir() will traverse subdirectories up to the depth specified.

        If depth is specified but not recursive, recursive is implied to be True.
        """
        if self._closed:
            self._raise_closed()
        try:
            for name in self._accessor.listdir(self):
                if name in {'.', '..'}:
                    # Yielding a path object for these makes little sense
                    continue
                child = self._make_child_relpath(name)
                if child.is_dir() and (depth > 0 or recursive):
                    for subchild in child.iterdir(depth = depth-1, recursive = recursive):
                        yield subchild
                else:
                    yield child
                if self._closed:
                    self._raise_closed()
        except:
            logging.debug('Could not read: ' + str(self))

    def move(self, destination: Union[str, Path], overwrite: bool = False, rename: str = None) -> None:
        _destination = Path(destination)

        if _destination.is_file() and not overwrite:
            raise FileExistsError(f"{_destination} exists")

        if _destination.is_dir() and not os.access(_destination, os.W_OK):
            raise PermissionError(f"{_destination} is not writable")

        # Get the destination directory
        directory: Path
        if _destination.is_file():
            directory = _destination.parent
        elif _destination.is_dir():
            directory = _destination

        # Get the destination filename
        filename: str
        if rename:
            filename = rename
        else:
            filename = _destination.name

        _destination = directory.joinpath(filename)

        shutil.move(self.path, destination)

    def delete(self):
        """
        Delete the file
        """
        remove(self)

class History:
    _path: str
    files: Set[OrganizedFile]
    shortcuts: Set[Shortcut]

    def __init__(self, path: Union[str, Path] = None):
        self._path = str(path)
        self.files = set()
        self.shortcuts = set()
        if path:
            self.load(path)

    @property
    def path(self) -> Path:
        if self._path:
            return Path(self._path)

        # Default path
        return Path.home().joinpath(".declutterpy.json")

    @path.setter
    def path(self, path: Union[str, Path]) -> None:
        _path: Path = Path(path)

        # Path must be an existing file
        if not _path.is_file():
            raise FileNotFoundError(_path)

    def _read_history(self, path: Union[str, Path] = None) -> dict:
        import json
        path = path or self.path
        data = json.load(open(path))
        history: dict = {"files": set(), "shortcuts": set()}
        for filepath in data.get("files", []):
            history["files"].add(OrganizedFile(filepath))
        for (key, directory) in data.get("shortcuts", {}).items():
            shortcut: Shortcut = Shortcut(key, directory)
            history["shortcuts"].add(shortcut)
        logging.info(f"history: files: {self.files}")
        logging.info(f"history: shortcuts: {self.shortcuts}")
        return history

    def load(self, path: Union[str, Path] = None) -> None:
        history = self._read_history(path)
        for file in history.get("files", set()):
            self.files.add(file)
        for shortcut in history.get("shortcuts", set()):
            self.shortcuts.add(shortcut)

    def save(self, path: Union[str, Path] = None, shortcuts: Set[Shortcut] = set(), files: Set[OrganizedFile] = set(), merge: bool = True) -> None:
        import json
        path = path or self.path
        files = files or self.files
        shortcuts = shortcuts or self.shortcuts

        # First try to open the history file. If we run into an error,
        # then there's no point in doing anything else
        with open(path, 'w') as history_file:
            if merge:
                history = self._read_history(path)
            else:
                history = {"files": set(), "shortcuts": {}}

            history["files"].update(files)
            history["shortcuts"].update(shortcuts)

            # Convert the files to a list for serialization
            history["files"] = list(history["files"])
            json.dump(history, history_file, indent=4, sort_keys=True)

class Organizer:
    _files: Set[OrganizedFile]
    shortcuts: Set[Shortcut]

    def __init__(self, files: Union[Iterable[OrganizedFile], Iterable[str], Iterable[Path]] = set(), shortcuts: Set[Shortcut] = set()):
        self.files = set([OrganizedFile(x) for x in files])
        self.shortcuts = shortcuts
    
    @property
    def files(self):
        # Return a copy of the file list to prevent direct editing
        return set(self._files)
    
    @files.setter
    def files(self, x):
        self._files = set(x)

    def move(self, source: Union[str, Path, OrganizedFile], destination: Union[str, Path], overwrite: bool = False) -> None:
        file: OrganizedFile = OrganizedFile(source)
        file.move(destination, overwrite)

    def get_shortcut(self, key) -> Optional[Shortcut]:
        for shortcut in self.shortcuts:
            if shortcut.key == key:
                return shortcut
        return None

    def iter(self, depth: int = 0, recursive: bool = False) -> Iterator[OrganizedFile]:
        for file in self.files:
            if file.is_dir() and (depth or recursive):
                for sub_file in file.iterdir(depth=depth - 1, recursive=recursive):
                    yield sub_file
            yield file

    def add(self, file: Union[Path, str, OrganizedFile]) -> None:
        self._files.add(OrganizedFile(file))

    def remove(self, file: Union[Path, str, OrganizedFile]) -> None:
        file = OrganizedFile(file)
        try:
            self.files.remove(file)
        except:
            pass
