"""Terminal output and prompting.

Everything informational goes to stderr so a command's real output can still be
redirected. Colour is enabled only when stderr is a terminal, and is turned on
explicitly on Windows, where ANSI handling is off by default in some consoles.
"""
import os
import sys


def _supports_colour():
    if not sys.stderr.isatty() or os.environ.get('NO_COLOR'):
        return False
    if sys.platform == 'win32':
        # Ask the console host to interpret ANSI escapes. Present on Windows 10+;
        # if it fails we simply go without colour.
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # -12 = STD_ERROR_HANDLE, 0x4 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
            return bool(kernel32.SetConsoleMode(kernel32.GetStdHandle(-12), 7))
        except Exception:
            return False
    return True


if _supports_colour():
    BLUE, GREEN, YELLOW, RED, BOLD, DIM, NC = (
        '\033[0;34m', '\033[0;32m', '\033[0;33m',
        '\033[0;31m', '\033[1m', '\033[2m', '\033[0m')
else:
    BLUE = GREEN = YELLOW = RED = BOLD = DIM = NC = ''


def say(message=''):
    print(message, file=sys.stderr)


def step(message):
    print("\n{}{}==>{} {}{}{}".format(BLUE, BOLD, NC, BOLD, message, NC), file=sys.stderr)


def ok(message):
    print("  {}ok{}   {}".format(GREEN, NC, message), file=sys.stderr)


def warn(message):
    print("  {}warn{} {}".format(YELLOW, NC, message), file=sys.stderr)


def bad(message):
    print("  {}FAIL{} {}".format(RED, NC, message), file=sys.stderr)


def detail(message):
    print("       {}{}{}".format(DIM, message, NC), file=sys.stderr)


class Abort(Exception):
    """Raised to stop a command cleanly.

    Carries an optional remedy so every failure can tell the operator what to do
    next, rather than leaving them with a bare error.
    """

    def __init__(self, message, fix=None):
        super().__init__(message)
        self.fix = fix


def die(message, fix=None):
    raise Abort(message, fix)


def _require_tty(what):
    if not sys.stdin.isatty():
        die("{} needs an interactive terminal, but input is not a terminal.".format(what),
            "Run this command directly in a terminal window.")


def confirm(prompt, expected=None):
    """Ask before doing something consequential.

    With `expected`, the operator must type that exact string. Used where a
    reflexive "y" should not be enough — production writes, mainly.
    """
    _require_tty("This command")

    if expected:
        say()
        say("{}{}{}".format(BOLD, prompt, NC))
        answer = input("Type '{}' to continue: ".format(expected)).strip()
        if answer != expected:
            die("Aborted — nothing was changed.")
    else:
        answer = input("{} [y/N]: ".format(prompt)).strip().lower()
        if answer not in ('y', 'yes'):
            die("Aborted — nothing was changed.")


def ask_yes_no(question, default=False):
    """Yes/no that returns a bool instead of aborting.

    For optional follow-ups, where "no" means "skip this", not "stop everything".
    """
    _require_tty("This command")
    hint = "[Y/n]" if default else "[y/N]"
    answer = input("{} {}: ".format(question, hint)).strip().lower()
    if not answer:
        return default
    return answer in ('y', 'yes')


def ask(question, default=None):
    """Prompt for free text. Re-asks until non-empty unless a default exists."""
    _require_tty("This command")
    suffix = " [{}]".format(default) if default else ""
    while True:
        answer = input("{}{}: ".format(question, suffix)).strip()
        if answer:
            return answer
        if default is not None:
            return default
        say("  (a value is required)")


def choose(question, options, allow_new=False):
    """Pick one of `options` by number.

    Used instead of free text wherever the value must match something that
    already exists — an indicator name in the database, a theme already in the
    config — because retyping those exactly is error-prone and the mismatch is
    silent.
    """
    _require_tty("This command")
    say()
    say("{}{}{}".format(BOLD, question, NC))
    for i, option in enumerate(options, 1):
        say("  {:>3}) {}".format(i, option))
    if allow_new:
        say("  {:>3}) (enter a new value)".format(len(options) + 1))

    limit = len(options) + (1 if allow_new else 0)
    while True:
        answer = input("Choose 1-{}: ".format(limit)).strip()
        if answer.isdigit() and 1 <= int(answer) <= limit:
            index = int(answer) - 1
            if allow_new and index == len(options):
                return ask("New value")
            return options[index]
        say("  (enter a number between 1 and {})".format(limit))
