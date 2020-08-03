# organizer-tui
A simple console program for quickly, efficiently organizing files

[![asciicast](https://asciinema.org/a/351451.svg)](https://asciinema.org/a/351451)

## About

organizer is called from the command line with any number of files/directories as arguments. The user then uses simple keystrokes to move each file to its desired location. Settings are saved for quicker start times, and filepaths are saved to optionally skip already-organized files in subsequent uses.

## Usage

#### Command line options

| option | description |
| --- | ----------- |
| -h/--help | show help message |
| --history filepath | use the given file for loading/saving shortcuts and filepaths |
| -i/--ignore-history | don't load a history file |
| -q/--quiet | be less verbose |

#### Keyboard controls

By default, when organizer launches, it prompts the user to enter a series of shortcuts in the format: `<single-char> <filepath>` eg: `d ~/Downloads`.

After shortcuts have been setup, each given file is listed. While organizing files, the following keys can be used:

| key | description |
| --- | ----------- |
| right | skip to the next file without saving |
| left | go back to the previous file |
| down | don't move this file, but store its location to skip it in the future |
| up | add a new shortcut |
| ? | show help message |
| &lt;single-char> | move the file to the directory associated with that shortcut key |

### TODO

- [ ] Implement the commented out command line options
  - [ ] Recursion with granular control over the depth
  - [ ] Specifically ignore filepath history
  - [ ] Specifically ignore shortcut history
  - [ ] Load history but don't save
  - [ ] Skip setup and jump straight to organizing
- [ ] Delete/Backspace stages file for deletion
  - [ ] Optionally delete without asking
- [ ] Mark files (don't do anything special, just print marked files out again after done)
- [ ] Code cleanup
  - [ ] Restructure a tad
  - [ ] Full documentation
  - [ ] Check type hinting coverage
- [ ] Automatically divine where I want my files to be and put them there
- [ ] Handle ctrl-c appropriately everywhere

#### Bugs

- [ ] tilde entered directly into config file not being loaded properly
- [ ] doesn't seem to always ask about overwriting files (probably due to the above)
