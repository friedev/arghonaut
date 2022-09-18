"""Entry points, argument parsing, and batch mode implementation."""

import argparse
import curses
from curses.ascii import EOT

from .common import read_lines
from .interface import ArghInterface, init_curses
from .interpreter import ArghInterpreter


# Command line arguments from argparse
# Stored globally so they can be passed into the curses wrapper
ARGS: argparse.Namespace


def batch_main(args: argparse.Namespace):
    """Main loop for batch mode."""
    interpreter = ArghInterpreter(read_lines(args.src.name))
    eof = False
    while not interpreter.done and not interpreter.error:
        interpreter.step(batch=True)
        if interpreter.needs_input:
            # Allow EOF to be entered only once
            if eof:
                print("Argh!", "tried to read input after EOF")
            else:
                try:
                    interpreter.input_string(input() + "\n")
                except EOFError:
                    interpreter.input_char(EOT)
                    eof = True

    if interpreter.error:
        print("Argh!", interpreter.error)


def interactive_main(stdscr: curses.window):
    """Main loop for interactive mode."""
    init_curses(stdscr)

    # Set up initial state
    code = read_lines(ARGS.src.name)
    interpreter = ArghInterpreter(code)
    interface = ArghInterface(interpreter, syntax=ARGS.syntax)
    interface.main(stdscr)


def main() -> None:
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
    args = parser.parse_args()

    # Batch mode (don't run curses)
    if args.batch:
        batch_main(args)
    # Interactive mode
    else:
        # Pass args into curses wrapper via interface.ARGS global
        global ARGS
        ARGS = args

        # Wrapper handles all curses setup, shutdown, and exception handling
        curses.wrapper(interactive_main)
