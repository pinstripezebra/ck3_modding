import pathlib
import re


# Required CK3 mod top-level layout
_REQUIRED_MOD_ITEMS = [
    "descriptor.mod",
    "common",
    "events",
    "localization",
]

# Valid CK3 trait category values (verified against game source)
_VALID_TRAIT_CATEGORIES = {
    "personality", "education", "childhood", "commander",
    "winter_commander", "lifestyle", "court_type", "fame", "health",
}

# Keys that are valid directly inside a trait block (non-exhaustive guard list)
_INVALID_TRAIT_BLOCKS = {"commander_modifier"}


def register(mcp, vectorstore):
    @mcp.tool()
    def validate_script(script: str) -> str:
        """Validate a CK3 script for common errors.
        Accepts either a file path to a .txt script file or inline script text.
        Checks:
          - UTF-8 BOM presence (must NOT be present in .txt files)
          - Brace balance
          - Empty assignments
          - Invalid trait categories
          - XP track thresholds above 100
          - 'commander_modifier' blocks inside trait definitions
          - Possibly unknown modifier/trigger names (doc lookup)
        Args:
            script: Path to a .txt script file, or inline CK3 script text.
        Returns:
            A newline-separated list of issues, or 'No issues found.'
        """
        raw_bytes: bytes | None = None
        candidate = pathlib.Path(script)
        if candidate.suffix == ".txt" and candidate.is_file():
            raw_bytes = candidate.read_bytes()
            script = raw_bytes.decode("utf-8", errors="replace")
        elif candidate.suffix == ".yml" and candidate.is_file():
            raw_bytes = candidate.read_bytes()
            script = raw_bytes.lstrip(b"\xef\xbb\xbf").decode("utf-8", errors="replace")

        issues = []

        # 1. BOM checks (file path only)
        if raw_bytes is not None:
            has_bom = raw_bytes[:3] == b"\xef\xbb\xbf"
            if candidate.suffix == ".txt" and has_bom:
                issues.append(
                    f"UTF-8 BOM present in .txt file '{candidate.name}' — "
                    "CK3 script files must NOT have a BOM (game logs a warning "
                    "and may fail to parse)"
                )
            if candidate.suffix == ".yml" and not has_bom:
                issues.append(
                    f"UTF-8 BOM MISSING in .yml file '{candidate.name}' — "
                    "localization files MUST have a UTF-8 BOM or CK3 ignores them"
                )

        # 2. Brace balance
        depth = 0
        for i, ch in enumerate(script):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth < 0:
                issues.append(f"Unexpected closing brace near char {i}")
                depth = 0
        if depth != 0:
            issues.append(f"Unclosed braces: {depth} block(s) not closed")

        # 3. Empty assignments (key = <nothing>)
        for lineno, line in enumerate(script.splitlines(), 1):
            stripped = line.strip()
            if re.fullmatch(r"[\w:]+\s*=\s*", stripped):
                issues.append(f"Line {lineno}: empty assignment — '{stripped}'")

        # 4. Invalid trait category values
        for m in re.finditer(r"\bcategory\s*=\s*(\w+)", script):
            cat = m.group(1)
            if cat not in _VALID_TRAIT_CATEGORIES:
                issues.append(
                    f"Invalid trait category '{cat}'. "
                    f"Valid values: {sorted(_VALID_TRAIT_CATEGORIES)}"
                )

        # 5. XP track thresholds above 100
        for m in re.finditer(r"^\s*(\d+)\s*=\s*\{", script, re.MULTILINE):
            val = int(m.group(1))
            if val > 100:
                issues.append(
                    f"Track XP threshold {val} exceeds the CK3 maximum of 100. "
                    "Use thresholds ≤ 100 (e.g. 33/66/100 for three tiers)."
                )

        # 6. commander_modifier inside trait blocks
        if re.search(r"\bcommander_modifier\s*=\s*\{", script):
            issues.append(
                "'commander_modifier = { }' is NOT valid inside a trait definition. "
                "Use direct modifier keys (e.g. 'advantage = 3') instead."
            )

        # 7. Cross-reference identifiers against docs (requires vectorstore)
        if vectorstore is not None:
            identifiers = re.findall(r"\b([a-z][a-z_]{3,})\s*=", script)
            if identifiers:
                unique_ids = list(dict.fromkeys(identifiers))
                query = "valid modifiers triggers effects: " + " ".join(unique_ids)
                docs = vectorstore.similarity_search(query, k=3)
                doc_text = " ".join(d.page_content for d in docs)
                for key in unique_ids:
                    if key not in doc_text:
                        issues.append(f"Possibly unknown key '{key}' (not found in docs)")

        return "\n".join(issues) if issues else "No issues found."

    @mcp.tool()
    def validate_localization(loc_path: str) -> str:
        """Validate a CK3 localization .yml file for common errors.
        Checks:
          - UTF-8 BOM present (required for all .yml loc files)
          - Starts with 'l_english:' header
          - Trait keys follow 'trait_X:0' format (not bare 'X:0')
          - No double-BOM
        Args:
            loc_path: Absolute path to a .yml localization file.
        Returns:
            A newline-separated list of issues, or 'No issues found.'
        """
        path = pathlib.Path(loc_path)
        if not path.is_file():
            return f"Error: file not found: {loc_path}"

        raw = path.read_bytes()
        issues = []

        # Double BOM check
        if raw[:6] == b"\xef\xbb\xbf\xef\xbb\xbf":
            issues.append(
                "Double UTF-8 BOM detected — file has been written with BOM twice. "
                "Strip one BOM to fix."
            )
        elif raw[:3] != b"\xef\xbb\xbf":
            issues.append(
                "Missing UTF-8 BOM — CK3 localization files must start with "
                "the byte sequence EF BB BF."
            )

        text = raw.lstrip(b"\xef\xbb\xbf").decode("utf-8", errors="replace")

        # Header check
        first_line = text.splitlines()[0].strip() if text.strip() else ""
        if not first_line.startswith("l_english:"):
            issues.append(
                f"First non-BOM line should be 'l_english:' but got: '{first_line}'"
            )

        # Trait key format check
        for lineno, line in enumerate(text.splitlines(), 1):
            m = re.match(r"^\s+(\w+):0\s", line)
            if m:
                key = m.group(1)
                # If it looks like a trait ID (no 'trait_' prefix, no known prefixes)
                known_prefixes = {
                    "trait_", "building_type_", "men_at_arms_type_",
                    "decision_", "interaction_", "perk_", "faith_",
                    "religion_", "culture_", "artifact_", "event_",
                }
                looks_like_trait_id = (
                    "_" in key
                    and not any(key.startswith(p) for p in known_prefixes)
                    and not key[0].isupper()
                    and not key.startswith("WIZARD_")
                    and not key.startswith("CHARACTER_")
                )
                if looks_like_trait_id:
                    issues.append(
                        f"Line {lineno}: key '{key}' may be a trait ID missing the "
                        f"'trait_' prefix. Expected 'trait_{key}:0' for trait names."
                    )

        return "\n".join(issues) if issues else "No issues found."

    @mcp.tool()
    def check_mod_structure(mod_path: str) -> str:
        """Verify a CK3 mod folder has the expected layout.
        Checks for descriptor.mod and required subdirectories.
        Args:
            mod_path: Absolute path to the mod folder.
        Returns:
            A report of missing files/folders, or 'Structure OK.'
        """
        mod_dir = pathlib.Path(mod_path)
        if not mod_dir.is_dir():
            return f"Error: '{mod_path}' is not a directory."

        issues = []

        for item in _REQUIRED_MOD_ITEMS:
            if not (mod_dir / item).exists():
                issues.append(f"Missing: {item}")

        # descriptor.mod must declare a name and supported_version
        descriptor = mod_dir / "descriptor.mod"
        if descriptor.is_file():
            content = descriptor.read_text(encoding="utf-8")
            for field in ("name=", "supported_version="):
                if field not in content:
                    issues.append(f"descriptor.mod missing field: {field.rstrip('=')}")

        # localization/ must have at least one language subfolder
        loc_dir = mod_dir / "localization"
        if loc_dir.is_dir() and not any(loc_dir.iterdir()):
            issues.append("localization/ has no language subdirectories (e.g. 'english')")

        return "\n".join(issues) if issues else "Structure OK."

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


def get_tools(vectorstore) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
def get_tools(vectorstore) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, vectorstore)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
