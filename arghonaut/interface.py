"""The curses interface to the Argh interpreter and surrounding setup."""

from copy import deepcopy
import curses
import sys

from .common import is_chr, is_printable, to_printable
from .interpreter import ArghInterpreter, COLUMNS


# Python curses does not define curses.COLOR_GRAY, even though it appears to be
# number 8 by default
COLOR_GRAY = 8

# UI colors
COLOR_DEFAULT = 0
COLOR_SPECIAL = 1
COLOR_DONE = 2
COLOR_ERROR = 3
COLOR_INPUT = 4
COLOR_OUTPUT = 5

# Syntax highlighting colors
COLOR_MOVEMENT = 6
COLOR_JUMP = 7
COLOR_IO = 8
COLOR_STACK = 9
COLOR_MATH = 10
COLOR_CONDITION = 11
COLOR_QUIT = 12
COLOR_COMMENT = 13

# Instruction categorization for syntax highlighting
COLOR_DICT: dict[str, int] = {
    "h": COLOR_MOVEMENT,
    "j": COLOR_MOVEMENT,
    "k": COLOR_MOVEMENT,
    "l": COLOR_MOVEMENT,
    "H": COLOR_JUMP,
    "J": COLOR_JUMP,
    "K": COLOR_JUMP,
    "L": COLOR_JUMP,
    "p": COLOR_IO,
    "P": COLOR_IO,
    "g": COLOR_IO,
    "G": COLOR_IO,
    "d": COLOR_STACK,
    "D": COLOR_STACK,
    "s": COLOR_STACK,
    "S": COLOR_STACK,
    "f": COLOR_STACK,
    "F": COLOR_STACK,
    "a": COLOR_MATH,
    "A": COLOR_MATH,
    "r": COLOR_MATH,
    "R": COLOR_MATH,
    "x": COLOR_CONDITION,
    "X": COLOR_CONDITION,
    "q": COLOR_QUIT,
    "#": COLOR_COMMENT,
}

BOLD_CHARS = "HJKLgGxXq"


class ArghInterface:
    """A curses interface to an Argh interpreter instance."""

    interpreter: ArghInterpreter
    syntax: bool
    code: list[list[int]]
    insert: bool
    auto: bool
    ex: int
    ey: int
    _render_start: int
    _old_x: int
    _old_y: int
    _old_ex: int
    _old_ey: int

    def __init__(self, interpreter: ArghInterpreter, syntax: bool = True):
        self.interpreter = interpreter
        self.syntax = syntax

        # Original code buffer
        self.code = deepcopy(self.interpreter.code)
        # Input state
        self.insert = False
        self.auto = False
        # Cursor
        self.ex = 0
        self.ey = 0
        # The line of code to start rendering at
        self._render_start = 0
        # Diagnostic and rendering information
        self._old_x = self.x
        self._old_y = self.y
        self._old_ex = self.ex
        self._old_ey = self.ey

    @property
    def x(self) -> int:
        """Shorthand for self.interpreter.x."""
        return self.interpreter.x

    @property
    def y(self) -> int:
        """Shorthand for self.interpreter.y."""
        return self.interpreter.y

    def move_cursor(self, x: int, y: int) -> None:
        """Move the editing cursor to the given cell, if valid."""
        if self.interpreter.is_valid(x, y):
            self.ex, self.ey = x, y

    def _update_render_range(self, stdscr: curses.window) -> None:
        """
        Update the start of the rendering range.

        The new start is based on the positions of the instruction pointer and
        the editing cursor, and whether or not they have moved since the last
        update.
        """
        cursor_moved = (self.ex, self.ey) != (self._old_ex, self._old_ey)
        pointer_moved = (self.x, self.y) != (self._old_x, self._old_y)
        if cursor_moved and self.ey < self._render_start:
            self._render_start = self.ey
        elif pointer_moved and self.y < self._render_start:
            self._render_start = self.y
        elif cursor_moved and self.ey >= self._render_end(stdscr):
            self._render_start = self.ey - self._render_height(stdscr) + 1
        elif pointer_moved and self.y >= self._render_end(stdscr):
            self._render_start = self.y - self._render_height(stdscr) + 1
        self._old_ex, self._old_ey = self.ex, self.ey
        self._old_x, self._old_y = self.x, self.y

    @property
    def _stack_text_length(self) -> int:
        """The string length of the stack symbols in their printable form."""
        length = 0
        for char in self.interpreter.stack:
            if is_printable(char, long=True):
                length += 1
            else:
                printable = to_printable(char, long=True)
                length += len(printable)
        return length

    def _bottom_rows(self, stdscr: curses.window) -> int:
        """
        The number of rows needed to display the bottom portion of the output.

        This includes stdout, stack, status, and padding.
        """
        stdout_list = self.interpreter.stdout.split("\n")
        stdout_lines = len(stdout_list)
        max_x = stdscr.getmaxyx()[1]
        for line in stdout_list:
            stdout_lines += len(line) // max_x
        stack_lines = self._stack_text_length // max_x
        return 9 + stdout_lines + stack_lines

    def _render_end(self, stdscr: curses.window) -> int:
        """Return the last (lowest) line to render."""
        return min(
            len(self.interpreter.code),
            self._render_start
            + stdscr.getmaxyx()[0]
            - self._bottom_rows(stdscr)
            + 1,
        )

    def _render_height(self, stdscr: curses.window) -> int:
        """Return the number of lines of code to be rendered."""
        return self._render_end(stdscr) - self._render_start

    def _render_char(
        self, stdscr: curses.window, x: int, y: int, highlight: bool = False
    ) -> None:
        """
        Render the character at the given code coordinates.

        Adjusts for render offsets.
        """
        # Don't render if out of bounds
        ry = y - self._render_start
        if ry < 0 or y > self._render_end(stdscr):
            return

        # Don't render spaces unless they're highlighted
        char = self.interpreter.code[y][x]
        if char == ord(" "):
            if highlight:
                attr = curses.color_pair(COLOR_DEFAULT)
                attr |= curses.A_REVERSE
                stdscr.addstr(ry, x, " ", attr)
            return

        # Normal printable character
        if is_printable(char):
            char_cast = chr(char)
            color_pair = COLOR_DEFAULT

            if self.syntax:
                color_pair = COLOR_DICT.get(char_cast, COLOR_DEFAULT)

                # Check if this character is commented (non-standard)
                if color_pair != COLOR_COMMENT:
                    for symbol in self.interpreter.code[y][:x]:
                        if (
                            is_printable(symbol)
                            and COLOR_DICT.get(chr(symbol)) == COLOR_COMMENT
                        ):
                            color_pair = COLOR_COMMENT
                            break

            attr = curses.color_pair(color_pair)

            # Bold important characters (outside of comments)
            if (
                self.syntax
                and color_pair != COLOR_COMMENT
                and char_cast in BOLD_CHARS
            ):
                attr |= curses.A_BOLD

            # Invert foreground and background colors on highlight (like vim)
            if highlight:
                attr |= curses.A_REVERSE

            stdscr.addstr(ry, x, char_cast, attr)

        # Special character
        else:
            color_pair = COLOR_SPECIAL
            attr = curses.color_pair(color_pair)
            # Invert foreground and background colors on highlight (like vim)
            if highlight:
                attr |= curses.A_REVERSE
            stdscr.addstr(
                ry, x, to_printable(char), curses.color_pair(color_pair)
            )

    def render(self, stdscr: curses.window) -> None:
        """
        Render the code and status output.
        """
        self._update_render_range(stdscr)

        # Render all visible code
        ry = 0
        for y in range(self._render_start, self._render_end(stdscr)):
            for x in range(len(self.interpreter.code[y])):
                # Highlight if instruction pointer or editing cursor is here
                highlight = (x, y) in ((self.x, self.y), (self.ex, self.ey))
                self._render_char(stdscr, x, y, highlight)
            ry += 1

        max_x = stdscr.getmaxyx()[1]

        # Standard output
        ry += 1
        stdscr.addstr(ry, 0, "Output:", curses.color_pair(COLOR_COMMENT))
        ry += 1
        stdout_list = self.interpreter.stdout.split("\n")
        for i in range(len(stdout_list)):
            stdscr.addstr(ry, 0, stdout_list[i])
            ry += len(stdout_list[i]) // max_x + 1

        # Stack, using printable characters
        ry += 1
        stdscr.addstr(ry, 0, "Stack:", curses.color_pair(COLOR_COMMENT))
        ry += 1
        x = 0
        for i in range(len(self.interpreter.stack)):
            char = self.interpreter.stack[i]
            if is_printable(char, long=True):
                stdscr.addstr(ry + (x // max_x), x % max_x, chr(char))
                x += 1
            else:
                printable = to_printable(char, long=True)
                stdscr.addstr(
                    ry + (x // max_x),
                    x % max_x,
                    printable,
                    curses.color_pair(COLOR_SPECIAL),
                )
                x += len(printable)

        # Status message
        ry += x // max_x
        ry += 2
        if self.interpreter.needs_input:
            stdscr.addstr(
                ry,
                0,
                "Type a character to input.",
                curses.color_pair(COLOR_INPUT),
            )
        elif self.interpreter.done:
            stdscr.addstr(ry, 0, "Done!", curses.color_pair(COLOR_DONE))
            ry += 1
            stdscr.addstr(ry, 0, "Press Q or Escape to exit.")
        elif self.interpreter.error:
            stdscr.addstr(ry, 0, "Argh!", curses.color_pair(COLOR_ERROR))
            ry += 1
            stdscr.addstr(ry, 0, self.interpreter.error)

    def handle_input(self, input_code: int) -> None:
        """Handle a single curses input code."""
        # In insert mode, always insert the next typed character
        if self.insert:
            self.interpreter.put(input_code, self.ex, self.ey)
            self.insert = False
            return

        # If input is needed, always input the next typed character
        if self.interpreter.needs_input:
            self.interpreter.input_char(input_code)
            self.interpreter.step()
            return

        # Otherwise, treat the typed character as a command
        # Parse input to a character for easier handling
        input_char = ""
        if is_chr(input_code):
            input_char = chr(input_code)

        # Toggle auto mode (0.1 second delay)
        if input_char == " ":
            self.auto = not self.auto
            if self.auto:
                curses.halfdelay(1)
                self.interpreter.step()
            else:
                curses.cbreak()

        # Step
        elif (
            input_char == "."
            or input_code == curses.ascii.LF
            or (self.auto and input_code == curses.ERR)
        ):
            self.interpreter.step()

        # Cursor left
        elif input_char == "h":
            self.move_cursor(self.ex - 1, self.ey)

        # Cursor right
        elif input_char == "l":
            self.move_cursor(self.ex + 1, self.ey)

        # Cursor up
        elif input_char == "k":
            self.move_cursor(self.ex, self.ey - 1)

        # Cursor down
        elif input_char == "j":
            self.move_cursor(self.ex, self.ey + 1)

        # Return the cursor to the instruction pointer
        elif input_char == "b":
            self.move_cursor(self.interpreter.x, self.interpreter.y)

        # Jump the instruction pointer to the cursor
        elif input_char == "g":
            self.interpreter.x, self.interpreter.y = (
                self.ex,
                self.ey,
            )

        # Enter insert mode
        elif input_char == "i":
            self.insert = True

        # Open a new line
        elif input_char == "o":
            self.interpreter.new_line()

        # Execute until blocked (no delay)
        elif input_char == "c":
            while not self.interpreter.blocked:
                self.interpreter.step()

        # Reset state (excluding unsaved code changes)
        elif input_char == "r":
            self.interpreter.reset()

        # Reset program (including unsaved code changes)
        elif input_char == "n":
            self.interpreter.code = self.code
            self.interpreter.reset()

        # Save current code changes to program state
        # Does not modify source file
        elif input_char == "s":
            self.code = deepcopy(self.interpreter.code)

        # Quit
        elif (
            input_char == "q"
            or input_code == curses.ascii.ESC
            or input_code == curses.ascii.EOT
        ):
            sys.exit(0)

    def main(self, stdscr: curses.window) -> None:
        """Run a main loop using this interface on the given screen."""
        input_code = None
        while True:
            self.render(stdscr)
            stdscr.refresh()

            try:
                input_code = stdscr.getch()
                # Block for input if auto mode is enabled
                while (
                    self.interpreter.needs_input
                    and self.auto
                    and input_code == curses.ERR
                ):
                    input_code = stdscr.getch()
            except KeyboardInterrupt:
                sys.exit(1)

            stdscr.erase()
            self.handle_input(input_code)


def init_color_pairs() -> None:
    """Initialize curses color pairs."""
    curses.init_pair(COLOR_DONE, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_ERROR, curses.COLOR_BLACK, curses.COLOR_RED)
    curses.init_pair(COLOR_INPUT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_OUTPUT, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_SPECIAL, curses.COLOR_BLACK, curses.COLOR_MAGENTA)

    curses.init_pair(COLOR_MOVEMENT, curses.COLOR_BLUE, -1)
    curses.init_pair(COLOR_JUMP, curses.COLOR_CYAN, -1)
    curses.init_pair(COLOR_IO, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_STACK, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_MATH, curses.COLOR_GREEN, -1)
    curses.init_pair(COLOR_CONDITION, curses.COLOR_MAGENTA, -1)
    curses.init_pair(COLOR_QUIT, curses.COLOR_RED, -1)
    curses.init_pair(COLOR_COMMENT, COLOR_GRAY, -1)


def init_curses(stdscr: curses.window) -> None:
    """Perform Arghonaut-specific curses initialization."""
    # Hide curses cursor
    curses.curs_set(0)

    # Allow using default terminal colors (-1 = default color)
    curses.use_default_colors()

    # Initialize color pairs
    init_color_pairs()

    # Require at least 80 characters to display Argh! programs
    if stdscr.getmaxyx()[1] < COLUMNS:
        # addstr will wrap the error message if the window is too small
        stdscr.addstr(0, 0, f"Argh! at least {COLUMNS} columns are required")
        stdscr.getch()
        sys.exit(1)
