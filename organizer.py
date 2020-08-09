#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Organizer TUI

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

import os
import _io
import sys
import json
import shutil
import readline
import argparse
from glob import glob
from pathlib import Path
from typing import Union, Tuple, Dict, Optional, List

# Setup settings
parser: argparse.ArgumentParser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
#parser.add_argument("-r", "--recursive", help="TODO", action="store_true")
#parser.add_argument("-d", "--depth", help="TODO", type=int, default=0)
parser.add_argument("--history", help="TODO", default=Path.home().joinpath(".organizer.json"))
parser.add_argument("-i", "--ignore-history", help="TODO", action="store_true")
#parser.add_argument("-S", "--ignore-history-shortcuts", help="TODO", action="store_true")
#parser.add_argument("-P", "--ignore-history-filepaths", help="TODO", action="store_true")
#parser.add_argument("-n", "--no-save", help="TODO", action="store_true")
#parser.add_argument("-s", "--skip-setup", help="TODO", action="store_true")
parser.add_argument("-q", "--quiet", help="TODO", action="store_true")
#parser.add_argument("-v", "--verbose", help="TODO", action="store_true")
parser.add_argument("paths", nargs="+", help="Files and directories to organize")
parser.epilog = __doc__
options: argparse.Namespace = parser.parse_args()

class ReservedShortcutException(Exception): pass
class EmptyInputException(Exception): pass
class InputFormatException(Exception): pass
class InvalidPathException(Exception): pass
class InsufficientPermissionsException(Exception): pass
class RenameException(Exception): pass

RESERVED_KEYS = "?-"

def load_history(path: Union[str, Path] = options.history) -> Dict[str, dict]:
    history: dict = {"shortcuts": {}, "savedpaths": {}}
    if not options.ignore_history:
        history_path: Path = Path(path)
        try:
            history = json.load(open(history_path))
        except Exception as e:
            if options.verbose:
                _output(f"Failed to load history file: {e}")

    # Ensure history dict has the necessary keys
    if not "shortcuts" in history:
        history["shortcuts"] = dict()
    if not "savedpaths" in history:
        history["savedpaths"] = list()

    return history

def update_history(shortcuts, savedpaths, path: Union[str, Path] = options.history) -> None:
    # Store shortcuts using absolute paths
    for key in shortcuts:
        shortcuts[key] = os.path.abspath(shortcuts[key])

    # Load previous history and merge with updates
    history: dict = load_history(path)
    updated: dict = {"shortcuts": shortcuts, "savedpaths": savedpaths}
    history["shortcuts"].update(shortcuts)
    history["savedpaths"].extend(savedpaths)

    # Save updated history as formatted json
    savefile: _io.TextIOWrapper = open(path, 'w')
    json.dump(history, savefile, indent=4, sort_keys=True)
    savefile.close()

# Returns a single byte from stdin (not necessarily the full keycode for
# certain special keys)
# https://gist.github.com/jasonrdsouza/1901709#gistcomment-2734411
def getch() -> str:
    def _getch() -> str:
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
    return _getch()
# Returns the (full) keycode for a single keypress from standard input
# https://pypi.org/project/readchar/
def getkey() -> str:
    c1 = getch()
    if ord(c1) != 0x1b:
        return c1
    c2 = getch()
    if ord(c2) != 0x5b:
        return c1 + c2
    c3 = getch()
    if ord(c3) != 0x33:
        return c1 + c2 + c3
    c4 = getch()
    return c1 + c2 + c3 + c4
 
# Method for tab completion
def _shortcut_completer(text, state) -> Optional[str]:
    buffer = readline.get_line_buffer()
    line = readline.get_line_buffer().split()
    # Only autocomplete the second item
    if len(line) != 2 and not buffer.endswith(" "):
        return None

    list_dir: str
    if not line or buffer.endswith(" "):
        list_dir = "."
    else:
        # Current entire filepath
        cur_path: str = os.path.expanduser(line[-1])
        list_dir = os.path.dirname(cur_path)
    term = text + "*"
    query = str(os.path.join(list_dir, term))
    files = glob(os.path.expanduser(query))
    matches = [Path(x).stem + os.path.sep for x in files if Path(x).is_dir()]
    if state < len(matches):
        return matches[state]
    else:
        return None

def input_filepath(prompt: str = "Enter a shortcut and path (empty line when done): ") -> str:
    readline.set_completer(_shortcut_completer)
    readline.parse_and_bind("tab: complete")
    return input(prompt)

def input_shortcut() -> Dict[str, str]:
    line = input_filepath()

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
    if char in RESERVED_KEYS:
        raise ReservedShortcutException(char)

    # Shortcut can only be one character
    if len(char) > 1:
        raise InputFormatException()

    # Path must exist and be a directory
    if not path.is_dir():
        raise InvalidPathException(path)

    # Directory must be writable
    if not os.access(path, os.W_OK):
        raise InsufficientPermissionsException()

    return {char: filepath}

def input_shortcuts() -> Dict[str, str]:
    shortcuts: Dict[str, str] = dict()
    finished: bool = False
    while not finished:
        try:
            shortcut = input_shortcut()
        except InputFormatException:
            _output("Please enter a single character followed by a directory, eg:", ignore_quiet=True)
            _output("d ~/Downloads", ignore_quiet=True)
        except InvalidPathException as e:
            _output(f"'{e}' is not a directory", ignore_quiet=True)
        except InsufficientPermissionsException:
            _output("You do not have sufficient permissions to move files there", ignore_quiet=True)
        except ReservedShortcutException as e:
            _output(f"The '{e}' character is reserved", ignore_quiet=True)
        except (EOFError, EmptyInputException):
            finished = True
        except Exception as e:
            _output(f"[error] {e}")
        else:
            shortcuts.update(shortcut)

    return shortcuts

def _handle_file_exists(filepath: Union[str, Path], destination: Union[str, Path]) -> str:
    filename: str = os.path.basename(filepath)
    filepath_new: str = os.path.join(destination, filename)

    while os.path.exists(filepath_new):
        should_rename: str = input(f"{filepath_new} exists! Rename? (y/n) ")
        
        if should_rename.lower().strip().startswith("y"):
            # Get new filename
            filename_new: str = input("Rename: ")
            filepath_new = os.path.join(destination, filename_new)
        else:
            raise RenameException()

    return filepath_new

def _output(*args, ignore_quiet: bool = False, **kwargs) -> None:
    if options.quiet and not ignore_quiet:
        return
    print(*args, **kwargs)

def _show_controls(shortcuts: Dict[str, str]) -> None:
    _output("Type one of the following shortcut keys to move a file to that location:", ignore_quiet=True)
    for shortcut in shortcuts.items():
        _output(f"- {shortcut[0]}: {shortcut[1]}")
    _output("", ignore_quiet=True)
    _output("Other keys:")
    _output("Left:  Go back to the previous file", ignore_quiet=True)
    _output("Right: Skip current file", ignore_quiet=True)
    _output("Up:    Add new shortcut(s)", ignore_quiet=True)
    if not options.ignore_history:
        _output(f"Down:  Save file's current location to {options.history}", ignore_quiet=True)
    _output("?:     This text", ignore_quiet=True)
    _output("For more information, use --help")


def _run() -> None:
    f = open('/tmp/log', 'a') # TODO

    shortcuts: Dict[str, str] = dict()
    savedpaths: List[str] = list()

    # Print usage if no files were given
    if not options.paths:
        parser.print_usage()
        quit()

    # Show list of files to be organized
    _output("Organizing files:")
    _output(", ".join(options.paths))
    _output("")

    # Potentially load and display history
    if not options.ignore_history:
        history: dict = load_history()
        # Update current shortcut and saved filepaths list
        if history.get("shortcuts"):
            shortcuts.update(history.get("shortcuts", {}))
            # Display previously used shortcuts
            _output("Loaded saved shortcuts:", ignore_quiet=True)
            if not options.quiet:
                for shortcut in history.get("shortcuts", dict()).items():
                    _output(f"- {shortcut[0]}: {shortcut[1]}")
            _output("", ignore_quiet=True)

    # Ask for a series of paths
    shortcuts.update(input_shortcuts())
    _output("")

    # If there are no shortcuts, tell the user to try again and exit
    if not shortcuts:
        _output("You must enter or load at least one shortcut! Exiting", ignore_quiet=True)
        sys.exit(1)

    # Iterate over files until last reached
    i = 0
    new_files = False
    _output("Type a shortcut key or ?:")
    while i < len(options.paths):
        # Shouldn't be able to set the index less than 0
        if i < 0:
            i = 0

        filestr: str = options.paths[i]
        # Get the next file in the sorting list
        f.write(str(i))
        f.write(str(filestr.encode()))
        f.flush()
        filepath: Path = Path(filestr)

        # Skip file if it's in our history file
        # (assume we've organized it before, and it's in its desired location)
        if not options.ignore_history:
            if os.path.abspath(filestr) in history.get("savedpaths", []):
                i += 1
                continue
            else:
                new_files = True

        _output(f"{filepath} -> ", end="")
        sys.stdout.flush()

        # Keep waiting for a character until the user types:
        # - a shortcut key in our list
        # - directional arrow key
        valid_key: bool = False
        while not valid_key:
            key: str = getkey()
            f.write(str(key.encode()))
            f.flush()

            if key == '?':
                valid_key = True
                _output("...", ignore_quiet=True)
                _show_controls(shortcuts)
            elif key == "-":
                valid_key = True
                try:
                    os.remove(filestr)
                except Exception as e:
                    _output(f"[error] Couldn't delete: {e}")
                else:
                    del options.paths[i]
                    _output("deleted!")
            elif key == "\r" or key == "\n":
                # try to preview the file
                try:
                    with open(filestr, 'r') as preview:
                        try:
                            import pydoc
                        except:
                            _output(preview.read(200), ignore_quiet=True)
                            _output(f"{filepath} -> ", end="", ignore_quiet=True)
                        else:
                            pydoc.pager(preview.read())
                except Exception as e:
                    _output(f"[error] Could not read file: {e}", ignore_quiet=True)
                    _output(f"{filepath} -> ", end="", ignore_quiet=True)
            elif key == "\x1b[A": # up arrow
                valid_key = True
                _output("...", ignore_quiet=True)
                s: Dict[str, str] = input_shortcuts()
                shortcuts.update(s)
                f.write(str(shortcuts))
                f.write("finished adding extra shortcuts")
                f.flush()
            elif key == "\x1b[B": # down arrow
                i += 1
                valid_key = True
                # Keep the file in its current location, effectively
                # skipping it, but storing the path to skip later
                savedpaths.append(os.path.abspath(filestr))
                _output(filestr, ignore_quiet=True)
            elif key == "\x1b[C": # right arrow
                i += 1
                valid_key = True
                # Skip the file
                _output("skipping...", ignore_quiet=True)
            elif key == "\x1b[D": # left arrow
                i -= 1
                valid_key = True
                # Go back
                _output("going back...", ignore_quiet=True)
            elif key in shortcuts:
                valid_key = True
                destination: Path = shortcuts.get(key) # type: ignore[assignment]

                # Check to see if the file exists
                try:
                    destination = Path(_handle_file_exists(filestr, destination))
                except RenameException:
                    i += 1
                    _output("skipping file...", ignore_quiet=True)
                    continue
                except Exception as e:
                    i += 1
                    _output(f"[error] {e}", ignore_quiet=True)
                    continue

                try:
                    filepath_new: str = shutil.move(filestr, os.path.expanduser(destination))
                except InsufficientPermissionsException:
                    _output("Insufficient permission to access:", destination, ignore_quiet=True)
                    _output("Please correct the permissions and try again, or skip this file (directional arrow keys)", ignore_quiet=True)
                except FileNotFoundError:
                    _output("File doesn't exist!", ignore_quiet=True)
                except shutil.Error as e:
                    _output(f"[error] {e}", ignore_quiet=True)
                else:
                    _output(filepath_new)
                    # Update the filepath in the list of files we're sorting in case the user goes back
                    options.paths[i] = os.path.abspath(filepath_new)
                    # Save the path to skip later
                    savedpaths.append(os.path.abspath(filepath_new))
                i += 1

    if not new_files:
        _output("No new files found! Use --help for more info", ignore_quiet=True)
    elif not options.ignore_history:
        update_history(shortcuts, savedpaths)
        _output("", ignore_quiet=True)
        _output(f"Saved filepaths and shortcuts to '{options.history}'", ignore_quiet=True)

if __name__ == '__main__':
    _run()