#!/usr/bin/env python3
"""Conservative Codex PreToolUse gate for common full-file shell reads."""
import ast
import itertools
import json
import os
from pathlib import Path
import re
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from settings import ConfigError, load_config, paused, setting


def python_read(argv):
    """Recognize only side-effect-free, literal `python -c 'print(file.read())'` reads."""
    if len(argv) != 3 or argv[1] != "-c":
        return []
    try:
        body = ast.parse(argv[2]).body
        if len(body) != 1 or not isinstance(body[0], ast.Expr):
            return []
        call = body[0].value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "print":
            return []
        paths = []
        for arg in call.args:
            if not isinstance(arg, ast.Call) or not isinstance(arg.func, ast.Attribute) or arg.args:
                return []
            if arg.func.attr not in ("read", "read_text", "read_bytes"):
                return []
            file_call = arg.func.value
            if not isinstance(file_call, ast.Call) or len(file_call.args) != 1:
                return []
            if not isinstance(file_call.args[0], ast.Constant) or not isinstance(file_call.args[0].value, str):
                return []
            filename = file_call.args[0].value
            if isinstance(file_call.func, ast.Name) and file_call.func.id == "open":
                paths.append(filename)
            elif (isinstance(file_call.func, ast.Name) and file_call.func.id == "Path"
                  and arg.func.attr in ("read_text", "read_bytes")):
                paths.append(filename)
            else:
                return []
        return paths
    except (SyntaxError, ValueError):
        return []


def read_paths(argv, limit):
    if not argv:
        return []
    cmd = Path(argv[0]).name
    args = argv[1:]
    if cmd in ("python", "python3"):
        return python_read(argv)
    if cmd in ("cat", "nl", "less", "more"):
        return [x for x in args if x != "-" and not x.startswith("-")]
    if cmd in ("head", "tail"):
        # Default 10 lines and explicit short ranges are targeted reads.
        count = 10
        filenames = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ("-n", "--lines") and i + 1 < len(args):
                i += 1
                try:
                    value = args[i]
                    count = int(value)
                    if (cmd == "tail" and value.startswith("+")) or (cmd == "head" and value.startswith("-")):
                        count = limit + 1
                    else:
                        count = abs(count)
                except ValueError:
                    return []
            elif re.fullmatch(r"-\d+", arg):
                count = int(arg[1:])
            elif arg.startswith("--lines="):
                try:
                    value = arg.split("=", 1)[1]
                    count = int(value)
                    if (cmd == "tail" and value.startswith("+")) or (cmd == "head" and value.startswith("-")):
                        count = limit + 1
                    else:
                        count = abs(count)
                except ValueError:
                    return []
            elif arg.startswith("-"):
                return []  # -c/--bytes and unfamiliar flags use other units.
            else:
                filenames.append(arg)
            i += 1
        return filenames if count > limit or count < 0 else []
    if cmd == "sed":
        if "-i" in args or "--in-place" in args:
            return []
        if "-n" not in args and "--quiet" not in args and "--silent" not in args:
            return args[1:] if args and not args[0].startswith("-") else []
        options = [arg for arg in args if arg not in ("-n", "--quiet", "--silent")]
        if len(options) < 2:
            return []
        script, *files = options
        match = re.fullmatch(r"(\d+),(\d+|\$)p", script)
        if script == "p" or (match and (match.group(2) == "$" or
                                            int(match.group(2)) - int(match.group(1)) + 1 > limit)):
            return files
        return []
    if cmd == "awk" and len(args) >= 2 and args[0].strip() in ("1", "{print}", "{print $0}"):
        return args[1:]
    return []


def decision(event):
    try:
        # A disabled Worker must not prevent Codex from reading source files.
        if paused(load_config()):
            return {}
        limit = int(setting("min_lines", 350))
        if limit < 1:
            raise ValueError()
    except ConfigError:
        return {}  # Misconfigured plugin must not block normal Codex reads.
    except (ValueError, TypeError):
        limit = 350
    tool_input = event.get("tool_input") or {}
    command = tool_input.get("command") or tool_input.get("cmd") or ""
    if isinstance(command, list) and all(isinstance(v, str) for v in command):
        argv = command
    elif isinstance(command, str) and command:
        # shortcut: compound commands may have side effects or filtered output;
        # only block straightforward reads, not arbitrary shell programs.
        if re.search(r"[|;&<>`]|\$\(", command):
            return {}
        try:
            argv = shlex.split(command)
        except ValueError:
            return {}
    else:
        return {}
    if len(argv) >= 3 and Path(argv[0]).name in ("bash", "sh", "zsh") and argv[1] in ("-lc", "-c"):
        return decision({"tool_input": {"command": argv[2]}, "cwd": event.get("cwd")})
    paths = read_paths(argv, limit)
    cwd = Path(event.get("cwd") or os.getcwd())
    for name in paths:
        path = cwd / name
        if not path.is_file():
            continue
        try:
            with path.open("rb") as stream:
                oversized = sum(1 for _ in itertools.islice(stream, limit + 1)) > limit
        except OSError:
            continue
        if oversized:
            reason = (f"{name} exceeds {limit} lines. Use the shunt bulk-reader skill for "
                      "summarization, or use a targeted read for exact edits.")
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                           "permissionDecision": "deny",
                                           "permissionDecisionReason": reason}}
    return {}


if __name__ == "__main__":
    try:
        print(json.dumps(decision(json.load(sys.stdin))))
    except (ValueError, TypeError, AttributeError):
        print("{}")
