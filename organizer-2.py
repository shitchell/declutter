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

__version__ = '0.1'

import os
import _io
import sys
import json
import shutil
import readline
from glob import glob
from pathlib import Path
from typing import Union, Tuple, Dict, Optional, List

class InvalidKeyException(Exception): pass
class InvalidShortcutException(Exception): pass

class OrganizedFile(type(Path())):
    """
    Subclass of pathlib.Path that tracks whether or not a file has been
    organized and is at its desired location.
    """
    _is_organized: bool

    def __init__(self, path: Union[str, Path], is_organized: bool = False):
        self._is_organized = is_organized

    @property
    def organized(self):
        return self._is_organized

    @organized.setter
    def organized(self, is_organized: bool):
        self._is_organized = is_organized

    def iterdir(self, depth: int = 0, recursive: bool = False) -> List[OrganizedFile]:
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
        elif _destination.is_directory():
            directory = _destination

        # Get the destination filename
        filename: str
        if rename:
            filename = rename
        else:
            filename = _destination.name

        _destination = directory.joinpath(filename)

        shutil.move(self.path, destination)

class Organizer:
    files: List[OrganizedFile]
    shortcuts: Dict[str, Path]

    def __init__(self, history: Union[str, Path] = ""):
        pass

    def move(self, source: Union[str, Path, OrganizedFile], destination: [str, Path], overwrite: bool = False) -> None:
        pass

class History:
    _path: str
    file: List[OrganizedFile]
    shortcuts: Dict[str, Path]

    def __init__(self, path: Union[str, Path]):
        self.path = path

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

    def load(self, path: Union[str, Path] = None) -> Dict[Dict[str, Path], List[OrganizedFile]]:
        pass

    def save(self, path: Union[str, Path] = None, shortcuts: List[Shortcut] = [], files: List[OrganizedFile] = [], overwrite: bool = False) -> bool:
        pass

class Shortcut:
    _key: str
    _path: Path

    def __init__(self, key: str, path: Union[str, Path]):
        self.key = key
        self.path = Path(path)

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
        retun {self._key: self._path}

def _run():
    import argparse

    # Setup settings
    parser: argparse.ArgumentParser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    #parser.add_argument("-r", "--recursive", help="TODO", action="store_true")
    #parser.add_argument("-d", "--depth", help="TODO", type=int, default=0)
    parser.add_argument("--history", help="TODO", default=Path.home().joinpath(".declutterpy.json"))
    parser.add_argument("-i", "--ignore-history", help="TODO", action="store_true")
    #parser.add_argument("-S", "--ignore-history-shortcuts", help="TODO", action="store_true")
    #parser.add_argument("-P", "--ignore-history-filepaths", help="TODO", action="store_true")
    #parser.add_argument("-n", "--no-save", help="TODO", action="store_true")
    #parser.add_argument("-s", "--skip-setup", help="TODO", action="store_true")
    parser.add_argument("-q", "--quiet", help="TODO", action="store_true")
    parser.add_argument("-v", "--verbose", help="TODO", action="count", default=0)
    parser.add_argument("paths", nargs="+", help="Files and directories to organize")
    parser.epilog = __doc__
    options: argparse.Namespace = parser.parse_args()

    def log(*args, level: int = 0, **kwargs):
        """
        Print statement that prints information based on verbosity level.
        """
        pass

    def getch() -> str:
        """
        Returns a single byte from stdin (not necessarily the full keycode for
        certain special keys)
        https://gist.github.com/jasonrdsouza/1901709#gistcomment-2734411
        """
        import os
        ch = ''
        if os.name == 'nt': # how it works on windows
            import msvcrt
            ch = msvcrt.getch() # type: ignore[attr-defined]
        else:
            import tty, termios, sys
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        if ord(ch) == 3:
            return "" # handle ctrl+C
        return ch

    def getkey() -> str:
        """
        Returns the (full) keycode for a single keypress from standard input
        https://pypi.org/project/readchar/
        """
        c1 = TUI.getch()
        if ord(c1) != 0x1b:
            return c1
        c2 = TUI.getch()
        if ord(c2) != 0x5b:
            return c1 + c2
        c3 = TUI.getch()
        if ord(c3) != 0x33:
            return c1 + c2 + c3
        c4 = TUI.getch()
        return c1 + c2 + c3 + c4

if __name__ == '__main__':

    TUI.run(options)