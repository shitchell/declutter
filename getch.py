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

