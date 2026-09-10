"""Parser for the Clausewitz script format used by Paradox game files.

The format is a sequence of `key OP value` statements, where value is either a
scalar or a `{ ... }` block containing more statements (or a bare list of
scalars). Keys may repeat within a block -- `prerequisite` appearing three times
is meaningful, not an error -- so blocks preserve order and duplicates rather
than collapsing into a dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

OPERATORS = ("==", ">=", "<=", "!=", "=", ">", "<")
_OP_CHARS = set("=<>!")


class ParseError(Exception):
    def __init__(self, message: str, path: Path | None = None, line: int | None = None):
        self.path = path
        self.line = line
        where = f"{path}:{line}: " if path and line else ""
        super().__init__(f"{where}{message}")


@dataclass
class Token:
    kind: str  # "text", "op", "{", "}"
    value: str
    line: int


def tokenize(text: str, path: Path | None = None) -> list[Token]:
    tokens: list[Token] = []
    i, line, n = 0, 1, len(text)

    while i < n:
        ch = text[i]

        if ch == "\n":
            line += 1
            i += 1
        elif ch.isspace():
            i += 1
        elif ch == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif ch in "{}":
            tokens.append(Token(ch, ch, line))
            i += 1
        elif ch == '"':
            start_line = i + 1
            i += 1
            buf = []
            while i < n and text[i] != '"':
                if text[i] == "\n":
                    line += 1
                buf.append(text[i])
                i += 1
            if i >= n:
                raise ParseError("unterminated quoted string", path, start_line)
            i += 1  # closing quote
            tokens.append(Token("text", "".join(buf), line))
        elif ch in _OP_CHARS:
            for op in OPERATORS:
                if text.startswith(op, i):
                    tokens.append(Token("op", op, line))
                    i += len(op)
                    break
            else:
                raise ParseError(f"unexpected character {ch!r}", path, line)
        else:
            start = i
            while i < n and not text[i].isspace() and text[i] not in '{}"#' and text[i] not in _OP_CHARS:
                i += 1
            tokens.append(Token("text", text[start:i], line))

    return tokens


@dataclass
class Block:
    """A `{ ... }` block: ordered statements plus any bare scalar values.

    `statements` holds (key, operator, value) triples where value is a str or a
    nested Block. `values` holds bare scalars, as in `{ 1 2 3 }` or
    `traits = { trait_a trait_b }`.
    """

    statements: list[tuple[str, str, "str | Block"]] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    line: int = 0
    # Malformed input that lenient parsing skipped over. Only ever set on the
    # root block, and worth surfacing: a script error is itself a defect.
    recovered: list[str] = field(default_factory=list)

    def get_all(self, key: str) -> list["str | Block"]:
        """Every value assigned to `key`, in file order. Duplicates matter here."""
        return [value for k, _, value in self.statements if k == key]

    def get(self, key: str, default=None):
        """The first value assigned to `key`."""
        found = self.get_all(key)
        return found[0] if found else default

    def get_scalar(self, key: str, default: str | None = None) -> str | None:
        value = self.get(key)
        return value if isinstance(value, str) else default

    def get_block(self, key: str) -> "Block | None":
        value = self.get(key)
        return value if isinstance(value, Block) else None

    def keys(self) -> list[str]:
        return [k for k, _, _ in self.statements]

    def has(self, key: str) -> bool:
        return any(k == key for k, _, _ in self.statements)

    def has_content(self, key: str) -> bool:
        """True when `key` is present *and* carries something.

        Paradox's focus template ships empty `bypass = { }` and `available = { }`
        stubs and authors routinely leave them in -- three quarters of the bypass
        blocks in vanilla are never filled. Treating an empty stub as present
        makes a tool claim conditions exist that cannot be tested.
        """
        for k, _, value in self.statements:
            if k != key:
                continue
            if isinstance(value, Block):
                if value.statements or value.values:
                    return True
            else:
                return True
        return False


def parse(text: str, path: Path | None = None, lenient: bool = False) -> Block:
    """Parse Clausewitz script.

    With `lenient=True`, two kinds of malformed input are recovered from and
    recorded rather than aborting the parse: a stray closing brace at file
    scope, and a block left unterminated at end of file. Vanilla ships both, the
    game tolerates both, and rejecting those files would lose every definition
    inside them -- silently under-reporting is the worst thing a QA tool can do.
    """
    tokens = tokenize(text, path)
    pos = 0
    recovered: list[str] = []

    def parse_block(is_root: bool, open_line: int) -> Block:
        nonlocal pos
        block = Block(line=open_line)

        while pos < len(tokens):
            token = tokens[pos]

            if token.kind == "}":
                if is_root:
                    if not lenient:
                        raise ParseError("unmatched closing brace", path, token.line)
                    recovered.append(f"line {token.line}: unmatched closing brace, skipped")
                    pos += 1
                    continue
                pos += 1
                return block

            if token.kind == "{":
                # An anonymous block inside a list, e.g. `{ { a = 1 } { b = 2 } }`.
                pos += 1
                parse_block(False, token.line)
                continue

            if token.kind == "op":
                raise ParseError(f"unexpected operator {token.value!r}", path, token.line)

            # token.kind == "text": either `key OP value` or a bare list value.
            if pos + 1 < len(tokens) and tokens[pos + 1].kind == "op":
                key, op = token.value, tokens[pos + 1].value
                pos += 2
                if pos >= len(tokens):
                    raise ParseError(f"missing value for {key!r}", path, token.line)

                value_token = tokens[pos]
                if value_token.kind == "{":
                    pos += 1
                    value: str | Block = parse_block(False, value_token.line)
                elif value_token.kind == "text":
                    value = value_token.value
                    pos += 1
                else:
                    raise ParseError(f"unexpected {value_token.value!r} after {key!r}", path, value_token.line)

                block.statements.append((key, op, value))
            else:
                block.values.append(token.value)
                pos += 1

        if not is_root:
            if not lenient:
                raise ParseError("unterminated block", path, open_line)
            recovered.append(f"line {open_line}: block never closed, terminated at end of file")
        return block

    root = parse_block(True, 1)
    root.recovered = recovered
    return root


def read_file(path: Path) -> str:
    """Read a Paradox script file, tolerating the encodings they ship."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_file(path: Path, lenient: bool = False) -> Block:
    return parse(read_file(path), path, lenient=lenient)
