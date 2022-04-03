"""The Argh interpreter and its program state."""

from collections import deque
from curses.ascii import EOT

from .common import is_chr, is_printable, to_printable


# Maximum columns; strict requirement of Argh! and Aargh!
COLUMNS = 80


class ArghInterpreter:
    """
    An instance of the Argh interpreter and its program state.

    Also tracks some editor information for ease of rendering.
    """

    def __init__(self, code):
        """
        Instantiate a new program with the given code.

        Code is converted into a 2D list of integer character codes.
        """
        self.code = []
        for y in range(len(code)):
            self.code.append([])
            for x in range(COLUMNS):
                if x < len(code[y]):
                    self.code[y].append(ord(code[y][x]))
                else:
                    self.code[y].append(ord(" "))

        # Instruction pointer
        self.x = 0
        self.y = 0
        # Direction
        self.dx = 0
        self.dy = 0
        # Stack and I/O
        self.stack = []
        self.stdout = ""
        self.stdin = deque()
        self.needs_input = False
        # Diagnostic and rendering information
        self.error = None

    def reset(self):
        """
        Reset all values of the program state other than code.
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
        self.stdin = deque()
        self.needs_input = False
        self.error = None

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

    def _get_above(self):
        """Get the symbol in the cell above the instruction pointer."""
        return self.get(self.x, self.y - 1)

    def _get_below(self):
        """Get the symbol in the cell below the instruction pointer."""
        return self.get(self.x, self.y + 1)

    def put(self, symbol, x, y):
        """Put the given symbol at the given coordinates, if they are valid."""
        if self.is_valid(x, y):
            self.code[y][x] = symbol

    def _put_above(self, symbol):
        """Put the given symbol in the cell above the instruction pointer."""
        self.put(symbol, self.x, self.y - 1)

    def _put_below(self, symbol):
        """Put the given symbol in the cell below the instruction pointer."""
        self.put(symbol, self.x, self.y + 1)

    def is_valid(self, x, y):
        """Are the given cell coordinates in the bounds of the program?"""
        return 0 <= y < len(self.code) and 0 <= x < len(self.code[y])

    def _move(self):
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
            return True

        self.error = "moved out of bounds"
        return False

    def _jump(self):
        """
        Jump to the next symbol matching the symbol at the top of the stack.

        The jump goes in the current direction of the instruction pointer.
        Errors if the stack is empty or the jump would take the instruction
        pointer out of bounds.
        """
        if not self.stack:
            self.error = "tried to pop from an empty stack"
            return

        if not self._move():
            self.error = "jumped out of bounds"
            return

        while self.instruction != self.stack[-1]:
            if not self._move():
                self.error = "jumped out of bounds"
                return

    def _print(self, char, batch=False):
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

    def _delete(self):
        """
        Delete the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack.pop()
        else:
            self.error = "tried to pop from an empty stack"

    def _duplicate(self):
        """
        Duplicate the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack.append(self.stack[-1])
        else:
            self.error = "tried to pop from an empty stack"

    def _add(self, addend):
        """
        Add the given value to the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack[-1] = self.stack[-1] + addend
        else:
            self.error = "tried to pop from an empty stack"

    def _subtract(self, subtrahend):
        """
        Subtract the given value from the top value of the stack.

        Errors if the stack is empty.
        """
        if self.stack:
            self.stack[-1] = self.stack[-1] - subtrahend
        else:
            self.error = "tried to pop from an empty stack"

    def _rotate(self, clockwise):
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
            self._jump()

        # Jump right
        elif instruction == "L":
            self.dx, self.dy = 1, 0
            self._jump()

        # Jump up
        elif instruction == "K":
            self.dx, self.dy = 0, -1
            self._jump()

        # Jump down
        elif instruction == "J":
            self.dx, self.dy = 0, 1
            self._jump()

        # Print above
        elif instruction == "P":
            self._print(self._get_above(), batch)

        # Print below
        elif instruction == "p":
            self._print(self._get_below(), batch)

        # Input above (blocks if input is not available)
        elif instruction == "G":
            if len(self.stdin) > 0:
                self._put_above(self.stdin.popleft())
            else:
                self.needs_input = True

        # Input below (blocks if input is not available)
        elif instruction == "g":
            if len(self.stdin) > 0:
                self._put_below(self.stdin.popleft())
            else:
                self.needs_input = True

        # Delete the top value from the stack
        elif instruction == "D":
            self._delete()

        # Duplicate the top value of the stack
        elif instruction == "d":
            self._duplicate()

        # Put EOF in the cell above
        elif instruction == "E":
            self._put_above(EOT)

        # Put EOF in the cell below
        elif instruction == "e":
            self._put_below(EOT)

        # Pop above
        elif instruction == "F":
            if self.stack:
                self._put_above(self.stack.pop())
            else:
                self.error = "tried to pop from an empty stack"

        # Pop below
        elif instruction == "f":
            if self.stack:
                self._put_below(self.stack.pop())
            else:
                self.error = "tried to pop from an empty stack"

        # Add the above value to the top value of the stack
        elif instruction == "A":
            self._add(self._get_above())

        # Add the below value to the top value of the stack
        elif instruction == "a":
            self._add(self._get_below())

        # Subtract the above value from the top value of the stack
        elif instruction == "R":
            self._subtract(self._get_above())

        # Subtract the below value from the top value of the stack
        elif instruction == "r":
            self._subtract(self._get_below())

        # Push above
        elif instruction == "S":
            self.stack.append(self._get_above())

        # Push below
        elif instruction == "s":
            self.stack.append(self._get_below())

        # Turn clockwise if the top value of the stack is negative
        elif instruction == "X":
            if self.stack:
                if self.stack[-1] < 0:
                    self._rotate(clockwise=False)
            else:
                self.error = "tried to pop from an empty stack"

        # Turn counter-clockwise if the top value of the stack is positive
        elif instruction == "x":
            if self.stack:
                if self.stack[-1] > 0:
                    self._rotate(clockwise=True)
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
            self._move()

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
