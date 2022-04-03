"""Common utilities for use in other modules."""

from curses.ascii import EOT


def read_lines(file_path):
    """
    Read the lines of the given file as a list of strings.

    Strips trailing newlines.
    """
    if not file_path:
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()
        return [line[:-1] for line in lines]


def is_chr(char):
    """
    Can the given character be cast to a chr?
    """
    try:
        chr(char)
        return True
    except ValueError:
        return False


def is_printable(char, long=False):
    """
    Can the given character be printed in a single cell with standard ASCII?

    Newlines and tabs are not included. In long output mode, spaces are not
    included due to ambiguity in output.
    """
    if long and char == ord(" "):
        return False
    return 32 <= char <= 126


def to_printable(char, long=False):
    """
    Converts the given character to a more readable/printable representation.

    In long output mode, this may be more than one character long. Printable
    characters are returned as-is.
    """
    escape = ""
    if is_printable(char):
        return chr(char)

    if 0 <= char <= 9:
        escape = str(char)
    elif char == ord("\n"):
        escape = "n"
    elif char == ord("\r"):
        escape = "r"
    elif char == ord("\t"):
        escape = "t"
    elif char == EOT:
        return "EOF" if long else "E"
    elif char < 0:
        return str(int(char)) if long else "-"
    else:
        return str(hex(char)) if long else "?"

    # Append a backslash to escape sequences in long output mode
    return "\\" + escape if long else escape
