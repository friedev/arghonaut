"""
Interactive Interpreter for Argh!
"""

__version__ = "1.4.0"

import argparse
import curses
import curses.ascii
import sys
import collections

# Command line arguments, set in main
ARGS = None

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
COLOR_DICT = {
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

# Maximum columns; strict requirement of Argh! and Aargh!
COLUMNS = 80


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
    Is the given character a standard ASCII character that can be printed in a
    single cell? Newlines and tabs are not included. In long output mode,
    spaces are not included due to ambiguity in output.
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
    elif char == curses.ascii.EOT:
        return "EOF" if long else "E"
    elif char < 0:
        return str(int(char)) if long else "-"
    else:
        return str(hex(char)) if long else "?"

    # Append a backslash to escape sequences in long output mode
    return "\\" + escape if long else escape


class State:
    """
    The program state. Also tracks some editor information for ease of
    rendering.
    """

    def __init__(self, code):
        """
        Instantiate a new program with the given code. Code is converted into a
        2D list of integer character codes.
        """
        self.code = []
        for y in range(len(code)):
            self.code.append([])
            for x in range(COLUMNS):
                if x < len(code[y]):
                    self.code[y].append(ord(code[y][x]))
                else:
                    self.code[y].append(ord(" "))

        # The line of code to start rendering at
        self.render_start = 0
        # Cursor
        self.ex = 0
        self.ey = 0
        # Instruction pointer
        self.x = 0
        self.y = 0
        # Direction
        self.dx = 0
        self.dy = 0
        # Stack and I/O
        self.stack = []
        self.stdout = ""
        self.stdin = collections.deque()
        self.needs_input = False
        # Diagnostic and rendering information
        self.error = None
        self.pointer_moved = False
        self.cursor_moved = False

    def reset(self):
        """
        Reset all values of the program state other than code and editor state.
        """
        # Instruction pointer
        self.x = 0
        self.y = 0
        # Direction
        self.dx = 0
        self.dy = 0
        # Stack and I/O
        self.stack = []
        self.stdout = ""
        self.stdin = collections.deque()
        self.needs_input = False
        # Diagnostic and rendering information
        self.error = None
        self.pointer_moved = False
        self.cursor_moved = False

    @property
    def instruction(self):
        """The symbol at the instruction pointer."""
        return self.code[self.y][self.x]

    @property
    def done(self):
        """True if the program has finished executing normally."""
        return self.instruction == ord("q")

    @property
    def blocked(self):
        """
        True if the program cannot currently execute further now.

        May be due to proper or improper termination or an input instruction.
        """
        return self.done or self.error or self.needs_input

    def get(self, x, y):
        """
        Return the symbol at (x, y) if it is a valid cell.

        x represents the row, and y represents the column.
        """
        return self.code[y][x] if self.is_valid(x, y) else None

    def get_above(self):
        """Get the symbol in the cell above the instruction pointer."""
        return self.get(self.x, self.y - 1)

    def get_below(self):
        """Get the symbol in the cell below the instruction pointer."""
        return self.get(self.x, self.y + 1)

    def put(self, symbol, x, y):
        """Put the given symbol at the given coordinates, if they are valid."""
        if self.is_valid(x, y):
            self.code[y][x] = symbol

    def put_above(self, symbol):
        """Put the given symbol in the cell above the instruction pointer."""
        self.put(symbol, self.x, self.y - 1)

    def put_below(self, symbol):
        """Put the given symbol in the cell below the instruction pointer."""
        self.put(symbol, self.x, self.y + 1)

    def is_valid(self, x, y):
        """Are the given cell coordinates in the bounds of the program?"""
        return 0 <= y < len(self.code) and 0 <= x < len(self.code[y])

    def move_cursor(self, x, y):
        """Move the editing cursor to the given cell, if valid."""
        if self.is_valid(x, y):
            self.ex, self.ey = x, y
        self.cursor_moved = True

    def update_render_range(self, stdscr):
        """
        Update the start of the rendering range.

        The new start is based on the positions of the instruction pointer and
        the editing cursor, and whether or not they have moved since the last
        update.
        """
        if self.cursor_moved and self.ey < self.render_start:
            self.render_start = self.ey
        elif self.pointer_moved and self.y < self.render_start:
            self.render_start = self.y
        elif self.cursor_moved and self.ey >= self.render_end(stdscr):
            self.render_start = self.ey - self.render_height(stdscr) + 1
        elif self.pointer_moved and self.y >= self.render_end(stdscr):
            self.render_start = self.y - self.render_height(stdscr) + 1
        self.cursor_moved = False
        self.pointer_moved = False

    @property
    def stack_text_length(self):
        """The string length of the stack symbols in their printable form."""
        length = 0
        for char in self.stack:
            if is_printable(char, long=True):
                length += 1
            else:
                printable = to_printable(char, long=True)
                length += len(printable)
        return length

    def bottom_rows(self, stdscr):
        """
        The number of rows needed to display the bottom portion of the output.

        This includes stdout, stack, status, and padding.
        """
        stdout_list = self.stdout.split("\n")
        stdout_lines = len(stdout_list)
        max_x = stdscr.getmaxyx()[1]
        for line in stdout_list:
            stdout_lines += len(line) // max_x
        stack_lines = self.stack_text_length // max_x
        return 9 + stdout_lines + stack_lines

    def render_end(self, stdscr):
        """Return the last (lowest) line to render."""
        return min(
            len(self.code),
            self.render_start
            + stdscr.getmaxyx()[0]
            - self.bottom_rows(stdscr)
            + 1,
        )

    def render_height(self, stdscr):
        """Return the number of lines of code to be rendered."""
        return self.render_end(stdscr) - self.render_start

    def render_char(self, stdscr, x, y, highlight=False):
        """
        Render the character at the given code coordinates.

        Adjusts for render offsets.
        """
        # Don't render if out of bounds
        ry = y - self.render_start
        if ry < 0 or y > self.render_end(stdscr):
            return

        # Don't render spaces unless they're highlighted
        char = self.code[y][x]
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

            if ARGS.syntax:
                color_pair = COLOR_DICT.get(char_cast, COLOR_DEFAULT)

                # Check if this character is commented (non-standard)
                if color_pair != COLOR_COMMENT:
                    for symbol in self.code[y][:x]:
                        if (
                            is_printable(symbol)
                            and COLOR_DICT.get(chr(symbol)) == COLOR_COMMENT
                        ):
                            color_pair = COLOR_COMMENT
                            break

            attr = curses.color_pair(color_pair)

            # Bold important characters (outside of comments)
            if (
                ARGS.syntax
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

    def render(self, stdscr):
        """
        Render the code and status output.
        """
        self.update_render_range(stdscr)

        # Render all visible code
        ry = 0
        for y in range(self.render_start, self.render_end(stdscr)):
            for x in range(len(self.code[y])):
                # Highlight if instruction pointer or editing cursor is here
                highlight = (x, y) in ((self.x, self.y), (self.ex, self.ey))
                self.render_char(stdscr, x, y, highlight)
            ry += 1

        max_x = stdscr.getmaxyx()[1]

        # Standard output
        ry += 1
        stdscr.addstr(ry, 0, "Output:", curses.color_pair(COLOR_COMMENT))
        ry += 1
        stdout_list = self.stdout.split("\n")
        for i in range(len(stdout_list)):
            stdscr.addstr(ry, 0, stdout_list[i])
            ry += len(stdout_list[i]) // max_x + 1

        # Stack, using printable characters
        ry += 1
        stdscr.addstr(ry, 0, "Stack:", curses.color_pair(COLOR_COMMENT))
        ry += 1
        x = 0
        for i in range(len(self.stack)):
            char = self.stack[i]
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
        if self.needs_input:
            stdscr.addstr(
                ry,
                0,
                "Type a character to input.",
                curses.color_pair(COLOR_INPUT),
            )
        elif self.done:
            stdscr.addstr(ry, 0, "Done!", curses.color_pair(COLOR_DONE))
            ry += 1
            stdscr.addstr(ry, 0, "Press Q or Escape to exit.")
        elif self.error:
            stdscr.addstr(ry, 0, "Argh!", curses.color_pair(COLOR_ERROR))
            ry += 1
            stdscr.addstr(ry, 0, self.error)

    def move(self):
        """
        Move the instruction pointer in the current direction.

        Errors if this movement would take the instruction pointer out of
        bounds, or if no direction was given (can only occur if this is the
        first symbol in the program).
        """
        if self.dx == 0 and self.dy == 0:
            self.error = "can't move; no direction specified"
            return False

        if self.is_valid(self.x + self.dx, self.y + self.dy):
            self.x += self.dx
            self.y += self.dy
            self.pointer_moved = True
            return True

        self.error = "moved out of bounds"
        return False

    def jump(self):
        """
        Jump to the next symbol matching the symbol at the top of the stack.

        The jump goes in the current direction of the instruction pointer.
        Errors if the stack is empty or the jump would take the instruction
        pointer out of bounds.
        """
        if not self.stack:
            self.error = "tried to pop from an empty stack"
            return

        if not self.move():
            self.error = "jumped out of bounds"
            return

        while self.instruction != self.stack[-1]:
            if not self.move():
                self.error = "jumped out of bounds"
                return

    def print(self, char, batch=False):
        """
        Prints the given character to stdout.

        Errors when trying to print an unprintable character.
        """
        if is_chr(char):
            self.stdout += chr(char)
            if batch:
                print(chr(char), end="")
        else:
            self.error = (
                "tried to print unprintable character: "
                f"{to_printable(char)}"
            )

    def input_char(self, char):
        """
        Provide the given character to standard input.

        To be called externally.
        """
        self.stdin.append(char)
        self.needs_input = False

    def input_string(self, string):
        """
        Provide all characters in the given string to standard input.

        To be called externally.
        """
        for char in string:
            self.input_char(ord(char))

    def delete(self):
        """
        Delete the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack.pop()
        else:
            self.error = "tried to pop from an empty stack"

    def duplicate(self):
        """
        Duplicate the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack.append(self.stack[-1])
        else:
            self.error = "tried to pop from an empty stack"

    def add(self, addend):
        """
        Add the given value to the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack[-1] = self.stack[-1] + addend
        else:
            self.error = "tried to pop from an empty stack"

    def subtract(self, subtrahend):
        """
        Subtract the given value from the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack[-1] = self.stack[-1] - subtrahend
        else:
            self.error = "tried to pop from an empty stack"

    def rotate(self, clockwise):
        """Rotates the current direction 90 degrees."""
        swap = self.dx
        self.dx = self.dy
        self.dy = swap

        if clockwise:
            self.dx = -self.dx
        else:
            self.dy = -self.dy

    def step(self, batch=False):
        """
        Performs one step of execution if the program is not blocked.

        Will print to the system's standard output in batch mode. Errors in
        various cases (see specific instruction comments).
        """
        if self.blocked:
            return

        # Parse the instruction to a character for easier handling
        instruction = self.instruction
        if not is_printable(instruction):
            self.error = f"invalid instruction: {to_printable(instruction)}"
        instruction = chr(instruction)

        # Set direction to left
        if instruction == "h":
            self.dx, self.dy = -1, 0

        # Set direction to right
        elif instruction == "l":
            self.dx, self.dy = 1, 0

        # Set direction to up
        elif instruction == "k":
            self.dx, self.dy = 0, -1

        # Set direction to down
        elif instruction == "j":
            self.dx, self.dy = 0, 1

        # Jump left
        elif instruction == "H":
            self.dx, self.dy = -1, 0
            self.jump()

        # Jump right
        elif instruction == "L":
            self.dx, self.dy = 1, 0
            self.jump()

        # Jump up
        elif instruction == "K":
            self.dx, self.dy = 0, -1
            self.jump()

        # Jump down
        elif instruction == "J":
            self.dx, self.dy = 0, 1
            self.jump()

        # Print above
        elif instruction == "P":
            self.print(self.get_above(), batch)

        # Print below
        elif instruction == "p":
            self.print(self.get_below(), batch)

        # Input above (blocks if input is not available)
        elif instruction == "G":
            if len(self.stdin) > 0:
                self.put_above(self.stdin.popleft())
            else:
                self.needs_input = True

        # Input below (blocks if input is not available)
        elif instruction == "g":
            if len(self.stdin) > 0:
                self.put_below(self.stdin.popleft())
            else:
                self.needs_input = True

        # Delete the top value from the stack
        elif instruction == "D":
            self.delete()

        # Duplicate the top value of the stack
        elif instruction == "d":
            self.duplicate()

        # Put EOF in the cell above
        elif instruction == "E":
            self.put_above(curses.ascii.EOT)

        # Put EOF in the cell below
        elif instruction == "e":
            self.put_below(curses.ascii.EOT)

        # Pop above
        elif instruction == "F":
            if self.stack:
                self.put_above(self.stack.pop())
            else:
                self.error = "tried to pop from an empty stack"

        # Pop below
        elif instruction == "f":
            if self.stack:
                self.put_below(self.stack.pop())
            else:
                self.error = "tried to pop from an empty stack"

        # Add the above value to the top value of the stack
        elif instruction == "A":
            self.add(self.get_above())

        # Add the below value to the top value of the stack
        elif instruction == "a":
            self.add(self.get_below())

        # Subtract the above value from the top value of the stack
        elif instruction == "R":
            self.subtract(self.get_above())

        # Subtract the below value from the top value of the stack
        elif instruction == "r":
            self.subtract(self.get_below())

        # Push above
        elif instruction == "S":
            self.stack.append(self.get_above())

        # Push below
        elif instruction == "s":
            self.stack.append(self.get_below())

        # Turn clockwise if the top value of the stack is negative
        elif instruction == "X":
            if self.stack:
                if self.stack[-1] < 0:
                    self.rotate(clockwise=False)
            else:
                self.error = "tried to pop from an empty stack"

        # Turn counter-clockwise if the top value of the stack is positive
        elif instruction == "x":
            if self.stack:
                if self.stack[-1] > 0:
                    self.rotate(clockwise=True)
            else:
                self.error = "tried to pop from an empty stack"

        # Behave as "j" if the character to the right is a "!"
        elif (
            instruction == "#"
            and self.x == 0
            and self.y == 0
            and self.get(1, 0) == ord("!")
        ):
            self.dx, self.dy = 0, 1

        # If the symbol is not any above instruction or "q", raise an error
        elif instruction != "q":
            # Invalid instruction
            self.error = f"invalid instruction: {instruction}"

        # Move the instruction pointer if execution is not blocked
        if not self.blocked:
            self.move()

    def new_line(self):
        """
        Appends a new blank line full of spaces to the code.

        For use in the editor.
        """
        self.code.append([ord(" ")] * COLUMNS)

    def code_to_string(self):
        """Convert the code to a string for exporting."""
        code = []
        for y in range(len(self.code)):
            code.append("")
            for x in range(len(self.code[y])):
                code[y] += chr(self.code[y][x])
        return code


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


def init_color_pairs():
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


def init_curses(stdscr):
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


def interactive_main(stdscr):
    """Main loop for interactive mode."""
    init_curses(stdscr)

    # Set up initial state
    code = read_lines(ARGS.src.name)
    state = State(code)
    insert = False
    auto = False
    input_code = None

    # Loop until user the exits
    while True:
        state.render(stdscr)

        stdscr.refresh()

        try:
            input_code = stdscr.getch()
            # Block for input if auto mode is enabled
            while state.needs_input and auto and input_code == curses.ERR:
                input_code = stdscr.getch()
        except KeyboardInterrupt:
            sys.exit(1)

        stdscr.erase()

        # In insert mode, always insert the next typed character
        if insert:
            state.put(input_code, state.ex, state.ey)
            insert = False

        # If input is needed, always input the next typed character
        elif state.needs_input:
            state.input_char(input_code)
            state.step()

        # Otherwise, treat the typed character as a command
        else:
            # Parse input to a character for easier handling
            input_char = ""
            if is_chr(input_code):
                input_char = chr(input_code)

            # Toggle auto mode (0.1 second delay)
            if input_char == " ":
                auto = not auto
                if auto:
                    curses.halfdelay(1)
                    state.step()
                else:
                    curses.cbreak()

            # Step
            elif (
                input_char == "."
                or input_code == curses.ascii.LF
                or (auto and input_code == curses.ERR)
            ):
                state.step()

            # Cursor left
            elif input_char == "h":
                if state.is_valid(state.ex - 1, state.ey):
                    state.move_cursor(state.ex - 1, state.ey)

            # Cursor right
            elif input_char == "l":
                if state.is_valid(state.ex + 1, state.ey):
                    state.move_cursor(state.ex + 1, state.ey)

            # Cursor up
            elif input_char == "k":
                if state.is_valid(state.ex, state.ey - 1):
                    state.move_cursor(state.ex, state.ey - 1)

            # Cursor down
            elif input_char == "j":
                if state.is_valid(state.ex, state.ey + 1):
                    state.move_cursor(state.ex, state.ey + 1)

            # Return the cursor to the instruction pointer
            elif input_char == "b":
                state.move_cursor(state.x, state.y)

            # Jump the instruction pointer to the cursor
            elif input_char == "g":
                state.x, state.y = state.ex, state.ey

            # Enter insert mode
            elif input_char == "i":
                insert = True

            # Open a new line
            elif input_char == "o":
                state.new_line()

            # Execute until blocked (no delay)
            elif input_char == "c":
                while not state.blocked:
                    state.step()

            # Reset state (excluding unsaved code changes)
            elif input_char == "r":
                state.reset()

            # Reset program (including unsaved code changes)
            elif input_char == "n":
                ex, ey = state.ex, state.ey
                state = State(code)
                state.move_cursor(ex, ey)

            # Save current code changes to program state
            # Does not modify source file
            elif input_char == "s":
                code = state.code_to_string()

            # Quit
            elif (
                input_char == "q"
                or input_code == curses.ascii.ESC
                or input_code == curses.ascii.EOT
            ):
                sys.exit(0)


def batch_main():
    """Main loop for batch mode."""
    state = State(read_lines(ARGS.src.name))
    eof = False
    while not state.done and not state.error:
        state.step(batch=True)
        if state.needs_input:
            # Allow EOF to be entered only once
            if eof:
                print("Argh!", "tried to read input after EOF")
            else:
                try:
                    state.input_string(input() + "\n")
                except EOFError:
                    state.input_char(curses.ascii.EOT)
                    eof = True

    if state.error:
        print("Argh!", state.error)


def main():
    """Entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Interactive Interpreter for Argh!"
    )
    parser.add_argument(
        "src",
        type=argparse.FileType("r"),
        help="the Argh! or Aargh! source file to run",
    )
    parser.add_argument(
        "-b",
        "--batch",
        action="store_true",
        help="run in batch mode (no visualizer)",
    )
    syntax_group = parser.add_mutually_exclusive_group()
    syntax_group.add_argument(
        "-s",
        "--syntax",
        dest="syntax",
        action="store_true",
        help="enable syntax highlighting (default)",
    )
    syntax_group.add_argument(
        "-S",
        "--no-syntax",
        dest="syntax",
        action="store_false",
        help="disable syntax highlighting",
    )
    parser.set_defaults(syntax=True)
    global ARGS
    ARGS = parser.parse_args()

    # Batch mode (don't run curses)
    if ARGS.batch:
        batch_main()
    # Interactive mode
    else:
        # Wrapper handles all curses setup, shutdown, and exception handling
        curses.wrapper(interactive_main)


if __name__ == "__main__":
    main()
