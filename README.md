# Arghonaut

Arghonaut is an interactive interpreter, visualizer, and debugger for [Argh! and Aargh!](https://esolangs.org/wiki/Argh!), which are [Befunge](https://esolangs.org/wiki/Befunge)-like esoteric programming languages designed by Sascha Wilde.
Arghonaut is written in Python and includes an ncurses interface.

Arghonaut was created by [Aaron Friesen](https://frie.dev) for FOSS Jam 2021, a hackathon hosted by the [UNL Operating Systems and Open Source Group](https://os2g.unl.edu).

## Installation

```sh
pip install arghonaut
```

To use the UI, make sure you have ncurses or a suitable equivalent installed.

## Usage

To run Arghonaut interactively, execute the following command, where `src.agh` is an Argh! or Aargh! source code file:

```sh
arghonaut src.agh
```

For more detailed usage information, run:

```sh
arghonaut --help
```

### Keybindings

Arghonaut supports the following keybindings:

- `.` or Enter: step through execution
- Space: automatically step through execution (0.1 second delay) or pause
- `c`: continue until next input
- `hjkl`: move the editing cursor
- `b`: return the cursor to the instruction pointer
- `g`: jump the instruction pointer to the cursor
- `i`: enter insert mode (the next character you type will be written into the code at the cursor position)
- `o`: open a new line
- `r`: reset state (excluding unsaved code changes)
- `n`: reset program (including unsaved code changes)
- `s`: save current code changes to program state (does not modify source file)
- `q` or Escape: quit

### Batch Mode

Arghonaut can be run in batch mode by adding the `--batch` flag.
In this mode, the curses interface will not be displayed, and input and output will be performed via standard input and standard output.
Programs can be run interactively with standard input from the keyboard, or with redirected or piped input.

## Examples

This repository includes some example Argh! and Aargh! programs written by Aaron Friesen.
For more examples, refer to the [Argh! Mercurial repository](http://hg.intevation.org/argh/file/tip/examples).

## Contributing

To run Arghonaut from source:

```sh
python -m arghonaut src.agh
```

If you want to submit a patch, please follow these guidelines:

- Run the project on some of the examples to test for bugs.
- Run some Python linters to check for and fix any coding style issues.

## License

Arghonaut is licensed under the [GNU General Public License Version 3](https://www.gnu.org/licenses/gpl-3.0.en.html).
Argh! is licensed under the [GNU General Public License Version 2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html), and permits the use of later versions of the license.
