import pathlib
import re


# Required CK3 mod top-level layout
_REQUIRED_MOD_ITEMS = [
    "descriptor.mod",
    "common",
    "events",
    "localization",
]


def register(mcp, vectorstore):
    @mcp.tool()
    def validate_script(script: str) -> str:
        """Validate a CK3 script for common errors.
        Accepts either a file path to a .txt script file or inline script text.
        Checks brace balance, empty assignments, and looks up suspicious
        modifier/trigger names against the documentation.
        Args:
            script: Path to a .txt script file, or inline CK3 script text.
        Returns:
            A newline-separated list of issues, or 'No issues found.'
        """
        # Auto-detect file path vs inline script
        candidate = pathlib.Path(script)
        if candidate.suffix == ".txt" and candidate.is_file():
            script = candidate.read_text(encoding="utf-8")

        issues = []

        # 1. Brace balance
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

        # 2. Empty assignments (key = <nothing>)
        for lineno, line in enumerate(script.splitlines(), 1):
            stripped = line.strip()
            if re.fullmatch(r'[\w:]+\s*=\s*', stripped):
                issues.append(f"Line {lineno}: empty assignment — '{stripped}'")

        # 3. Cross-reference identifiers against docs
        identifiers = re.findall(r'\b([a-z][a-z_]{3,})\s*=', script)
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
