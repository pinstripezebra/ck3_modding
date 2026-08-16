import pathlib
import re
from collections import Counter
from typing import Optional


_CK3_SUBPATH = pathlib.Path("Paradox Interactive") / "Crusader Kings III" / "logs" / "error.log"
_ENTRY_RE = re.compile(r"^\[(?P<time>[^\]]+)\]\[(?P<level>[EWI])\]\[(?P<source>[^\]]+)\]:\s?(?P<message>.*)$")


def _default_error_log_path() -> Optional[pathlib.Path]:
    candidates = [
        pathlib.Path.home() / "OneDrive" / "Documents" / _CK3_SUBPATH,
        pathlib.Path.home() / "Documents" / _CK3_SUBPATH,
    ]

    user_profile = pathlib.Path.home()
    if "USERPROFILE" in __import__("os").environ:
        user_profile = pathlib.Path(__import__("os").environ["USERPROFILE"])
    candidates.append(user_profile / "OneDrive" / "Documents" / _CK3_SUBPATH)
    candidates.append(user_profile / "Documents" / _CK3_SUBPATH)

    for path in candidates:
        if path.is_file():
            return path
    return None


def _resolve_log_path(log_path: Optional[str]) -> pathlib.Path:
    if log_path:
        path = pathlib.Path(log_path)
    else:
        inferred = _default_error_log_path()
        if inferred is None:
            raise FileNotFoundError(
                "Could not locate CK3 error.log automatically. Provide log_path explicitly."
            )
        path = inferred

    if not path.is_file():
        raise FileNotFoundError(f"Error log not found: {path}")
    return path


def register(mcp):
    @mcp.tool()
    def load_error_log(
        log_path: Optional[str] = None,
        max_lines: int = 200,
        level: Optional[str] = None,
        contains: Optional[str] = None,
    ) -> str:
        """Load CK3 error.log lines with optional filtering.
        Args:
            log_path: Optional explicit path to error.log. If omitted, tries
                      common CK3 Documents locations.
            max_lines: Maximum number of lines to return from the end of file.
            level: Optional one-letter severity filter: E, W, or I.
            contains: Optional case-insensitive substring filter.
        Returns:
            A newline-separated excerpt from the log.
        """
        path = _resolve_log_path(log_path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

        token = level.upper().strip() if level else None
        if token and token not in {"E", "W", "I"}:
            return "Error: level must be one of E, W, I"

        filtered = lines
        if token:
            filtered = [ln for ln in filtered if f"][{token}][" in ln]
        if contains:
            needle = contains.lower()
            filtered = [ln for ln in filtered if needle in ln.lower()]

        tail = filtered[-max(1, int(max_lines)) :]
        if not tail:
            return f"No matching lines found in {path}"
        return "\n".join(tail)

    @mcp.tool()
    def parse_error_log(
        log_path: Optional[str] = None,
        max_lines: int = 5000,
        focus: Optional[str] = None,
    ) -> str:
        """Parse CK3 error.log and return a compact issue summary.
        Args:
            log_path: Optional explicit path to error.log. If omitted, tries
                      common CK3 Documents locations.
            max_lines: Number of recent lines to parse.
            focus: Optional case-insensitive keyword to filter summary and
                   recent entries (e.g. 'wizard_mana').
        Returns:
            A human-readable summary with severity counts, top sources, and
            recent matching entries.
        """
        path = _resolve_log_path(log_path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        window = lines[-max(1, int(max_lines)) :]

        focus_token = focus.lower().strip() if focus else None

        level_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        message_counts: Counter[str] = Counter()
        parsed_entries = []

        for line in window:
            match = _ENTRY_RE.match(line)
            if not match:
                continue

            entry = match.groupdict()
            if focus_token and focus_token not in line.lower():
                continue

            lvl = entry["level"]
            src = entry["source"]
            msg = entry["message"]
            level_counts[lvl] += 1
            source_counts[src] += 1
            message_counts[msg] += 1
            parsed_entries.append(line)

        if not parsed_entries:
            suffix = f" for focus '{focus}'" if focus else ""
            return f"No parsable log entries found in {path}{suffix}."

        lines_out = [
            f"Log: {path}",
            f"Parsed entries: {len(parsed_entries)} (from last {len(window)} lines)",
            f"Severity counts: E={level_counts.get('E', 0)} W={level_counts.get('W', 0)} I={level_counts.get('I', 0)}",
            "Top sources:",
        ]

        for src, count in source_counts.most_common(8):
            lines_out.append(f"- {src}: {count}")

        lines_out.append("Top repeated messages:")
        for msg, count in message_counts.most_common(8):
            lines_out.append(f"- ({count}x) {msg}")

        lines_out.append("Recent entries:")
        for line in parsed_entries[-12:]:
            lines_out.append(f"- {line}")

        return "\n".join(lines_out)

# -- LangChain tool factory -------------------------------------------------

class _ToolCollector:
    """Mimics FastMCP so register() populates tools without a real server."""
    def __init__(self):
        self._fns: list = []
    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn
        return _wrap


def get_tools() -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
