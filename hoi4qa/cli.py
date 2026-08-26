"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checklist import build_checklist, find_tree
from .checks import ERROR, INFO, WARNING, Finding, run_all
from .model import FocusData, load_directory

_SEVERITIES = (ERROR, WARNING, INFO)
_SYMBOL = {ERROR: "!", WARNING: "~", INFO: "-"}


def _filter(findings: list[Finding], min_severity: str) -> list[Finding]:
    cutoff = _SEVERITIES.index(min_severity)
    return [f for f in findings if _SEVERITIES.index(f.severity) <= cutoff]


def _summary(findings: list[Finding]) -> str:
    counts = {severity: sum(1 for f in findings if f.severity == severity) for severity in _SEVERITIES}
    return f"{counts[ERROR]} error(s), {counts[WARNING]} warning(s), {counts[INFO]} info"


def _render_text(data: FocusData, findings: list[Finding]) -> str:
    lines = [
        f"Scanned {data.files_read} file(s): {len(data.trees)} tree(s), "
        f"{len(data.all_focuses)} focus(es)",
        _summary(findings),
        "",
    ]

    if data.parse_errors:
        lines.append(f"Parse failures ({len(data.parse_errors)}):")
        lines.extend(f"  {error}" for error in data.parse_errors)
        lines.append("")

    current_category = None
    for finding in findings:
        if finding.category != current_category:
            current_category = finding.category
            lines.append(f"[{current_category}]")
        lines.append(
            f" {_SYMBOL[finding.severity]} {finding.focus_id} ({finding.location}): {finding.message}"
        )

    if not findings:
        lines.append("No findings.")

    return "\n".join(lines) + "\n"


def _render_markdown(data: FocusData, findings: list[Finding]) -> str:
    lines = [
        "# Focus tree QA report",
        "",
        f"Scanned **{data.files_read}** file(s): {len(data.trees)} tree(s), "
        f"{len(data.all_focuses)} focus(es).",
        "",
        f"**{_summary(findings)}**",
        "",
    ]

    if data.parse_errors:
        lines += ["## Parse failures", ""]
        lines += [f"- `{error}`" for error in data.parse_errors]
        lines.append("")

    if not findings:
        lines += ["No findings."]
        return "\n".join(lines) + "\n"

    lines += ["| Severity | Check | Focus | Location | Detail |", "| --- | --- | --- | --- | --- |"]
    for finding in findings:
        detail = finding.message.replace("|", "\\|")
        lines.append(
            f"| {finding.severity} | {finding.category} | `{finding.focus_id}` "
            f"| `{finding.location}` | {detail} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def _write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"wrote {output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hoi4qa",
        description="Static QA checks and test-checklist generation for Hearts of Iron IV focus trees.",
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Game or mod root (containing common/national_focus), or a focus directory itself",
    )
    parser.add_argument("--checklist", metavar="TREE", help="Generate a test checklist for a tree id or country tag")
    parser.add_argument("--list-trees", action="store_true", help="List the trees found and exit")
    parser.add_argument("--format", choices=("text", "md"), default="text")
    parser.add_argument("--severity", choices=_SEVERITIES, default=WARNING, help="Minimum severity to report")
    parser.add_argument("-o", "--output", help="Write to this file instead of stdout")
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero when any error-severity finding is present (for CI)",
    )
    args = parser.parse_args(argv)

    data = load_directory(args.directory)

    if not data.files_read and data.parse_errors:
        print("\n".join(data.parse_errors), file=sys.stderr)
        return 2

    if args.list_trees:
        for tree in sorted(data.trees, key=lambda t: t.id):
            tag = f" [{tree.country_tag}]" if tree.country_tag else ""
            print(f"{tree.id}{tag}  {len(tree.focuses)} focuses  ({tree.path.name})")
        return 0

    if args.checklist:
        tree = find_tree(data, args.checklist)
        if tree is None:
            print(f"no tree matching '{args.checklist}' -- try --list-trees", file=sys.stderr)
            return 2
        _write("\n".join(build_checklist(tree)), args.output)
        return 0

    findings = _filter(run_all(data), args.severity)
    render = _render_markdown if args.format == "md" else _render_text
    _write(render(data, findings), args.output)

    if args.fail_on_error and any(f.severity == ERROR for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
