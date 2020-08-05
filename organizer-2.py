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
from typing import Union, Tuple, Dict, Optional, List, Iterable, Callable

class ReservedShortcutException(Exception): pass
class InputFormatException(Exception): pass
class EmptyInputException(Exception): pass
class InvalidKeyException(Exception): pass
class InvalidShortcutException(Exception): pass

class OrganizedFile(type(Path())): # type: ignore
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

class Organizer:
    files: List[OrganizedFile]
    shortcuts: Dict[str, Path]
    _history: History

    def __init__(self, history: Union[str, Path] = None):
        pass

    def move(self, source: Union[str, Path, OrganizedFile], destination: Union[str, Path], overwrite: bool = False) -> None:
        pass

    def get_shortcut(self, key) -> Optional[Shortcut]:
        path: Optional[Path] = self.shortcuts.get(key)
        if path:
            return Shortcut(key, path)
        return None

class History:
    _path: str
    files: List[OrganizedFile]
    shortcuts: Dict[str, Path]

    def __init__(self, path: Union[str, Path] = None):
        self._path = str(path)
        if not path:
            self.files = []
            self.shortcuts = {}
        else:
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

    def __str__(self):
        return f"{self._key}: {_self.path}"

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

class TUI:
    import argparse

    options: argparse.Namespace
    _parser: argparse.ArgumentParser
    _history: History
    _organizer: Organizer
    _key_actions: Dict[str, str] = {
        "?": "help",
        "-": "delete",
        "\r": "preview",
        "\n": "preview"
    }
    V_MAX = 6 # Only print if verbose
    V_DEF = 3 # Default verbosity
    V_MIN = 0 # Minimum required for functionality

    def __init__(self, args: List[str] = None):
        self._parse_args(args)
        self._history = History()
        self._organizer = Organizer()

    def _parse_args(self, args: List[str] = None):
        import argparse

        # Setup settings
        parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
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
        
        # Parse provided options if given, else command line options
        if args:
            self.options = parser.parse_args(args)
        else:
            self.options = parser.parse_args()

    @staticmethod
    def _shortcut_completer(text: str, state: int) -> Optional[str]:
        buffer = readline.get_line_buffer()
        line = readline.get_line_buffer().split()

        # Only autocomplete the second item
        if len(line) != 2 and not buffer.endswith(" "):
            return None

        # Get the base directory typed
        list_dir: str
        if not line or buffer.endswith(" "):
            list_dir = "."
        else:
            # Current entire filepath
            cur_path: str = os.path.expanduser(line[-1])
            list_dir = os.path.dirname(cur_path)

        # Put together the base directory, filename, and an asterisk
        term = text + "*"
        query = str(os.path.join(list_dir, term))
        files = glob(os.path.expanduser(query))
        matches = [Path(x).stem + os.path.sep for x in files if Path(x).is_dir()]
        if state < len(matches):
            return matches[state]
        else:
            return None

    def input_shortcut(self, prompt: str = "") -> Dict[str, Path]:
        """
        Input that accepts a single character followed by a filepath, eg:

        $ a /path/to/file
        
        Provides filepath completion, eg:

        $ p ~/Down<tab>
        becomes
        $ p ~/Downloads
        """
        readline.set_completer(TUI._shortcut_completer)
        readline.parse_and_bind("tab: complete")

        line: str = input(prompt)
        # Empty line given
        if not line.strip():
            raise EmptyInputException()

        parts: list = line.split(maxsplit=1)

        # Must be 2 words/parts
        if len(parts) != 2:
            raise InputFormatException()

        # Collect the parts
        char: str = parts[0]
        filepath: str = parts[1]
        path: Path = Path(filepath).expanduser()

        # Cannot use reserved keys
        if char in self._key_actions:
            raise ReservedShortcutException(char)

        # Shortcut can only be one character
        if len(char) > 1:
            raise InputFormatException()

        # Path must exist and be a directory
        if not path.is_dir():
            raise NotADirectoryError(path)

        # Directory must be writable
        if not os.access(path, os.W_OK):
            raise PermissionError(path)

        return {char: path}

    def printv(self, *args, level: int = 0, **kwargs):
        """
        Prints information based on an integer verbosity level. 3 variables are
        defined to distinguish the main types of output:

        TUI.V_MAX -> Print when verbose
        TUI.V_DEF -> Default setting
        TUI.V_MIN -> Only the minimum required to function
        """
        if level <= self.options.level:
            print(*args, **kwargs)

    @staticmethod
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

    @staticmethod
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

    def _print_startup_information(self):
        printv()
 
   # Interactive file organization actions
    def _get_action(self, action):
        if hasattr(self, "do_" + action):
            return getattr(self, "do_" + action)

    def do_delete(self, ctx):
        ctx.get('file').delete()

    def organize_files(self):
        """
        Loop over the organizer's list of files, using keyboard commands to
        manipulate file locations
        """
        i: int = 0
        new_files: bool = False
        organized_count = 0
        printv("Type a shortcut key or ?:", level=TUI.V_DEF)
        for i in range(len(self._organizer.files)):
            # Never let the file index drop below 0
            if i < 0:
                i = 0

            i = True

            # Get the next file
            file: OrganizedFile = self._organizer.files[i]
            printv(f"{file} -> ", level=TUI.V_MIN)

            # Get a single keypress from the user
            valid_key: bool = False
            while not valid_key:
                key: str = TUI.getkey()

                # See if there is a shortcut associated with the key
                action: str
                shortcut: Shortcut = self._organizer.get_shortcut(key)
                if shortcut:
                    action = "move"
                else:
                    action = TUI._key_actions.get(key)
                action_func: Callable = self._get_action(action)

                if func:
                    try:
                        action_func(locals())
                    except Exception as e:
                        printv(f"[error] {e}", level=TUI.V_MIN)
                    else:
                        valid_key = True
                else:
                    # key pressed is not associated with an action or shortcut
                    pass

    def run(self):
        """
        Launch a text based interface to organize files
        """
        # Startup info -> Number of files passed in and saved shortcuts
        if not self.options.skip_setup:
            printv("Processing {} files".format(len(self._organizer.files)), level=V_DEF)
            printv("", level=V_DEF)
            printv("Loaded shortcuts:", level=V_DEF)
            for shortcut in self._history.shortcuts:
                print(f"- {shortcut}")

        # Setup shortcuts
        if not self.options.skip_setup:
            empty_or_EOF = False
            while not empty_or_EOF:
                try:
                    shortcut = self.input_shortcut("Enter a shortcut and path (empty line when done):")
                except (EOFError, EmptyInputException):
                    empty_or_EOF = True
                except InputFormatException:
                    printv("Shortcut must be a single character followed by a file path, eg: d ~/Downloads", level=TUI.V_DEF)
                except InvalidPathException as e:
                    printv(f"{e} is not a directory", level=TUI.V_DEF)
                except PermissionError as e:
                    printv(f"You do not have permission to access {e}", level=TUI.V_DEF)
                else:
                    self._organizer.shortcuts.update(shortcut)

        # Start organizing files
        i: int = 0
        new_files: bool = False
        printv("Type a shortcut key or ?:", level=TUI.V_DEF)
        for i in range(len(self._organizer.files)):
            # Never let the file index drop below 0
            if i < 0:
                i = 0

            i = True

            # Get the next file
            file: OrganizedFile = self._organizer.files[i]

    # Organize files
if __name__ == '__main__':
    TUI().run()
