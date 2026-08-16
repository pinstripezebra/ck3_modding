import pathlib
from typing import Optional


def _emit_block(lines: list[str], header: str, body: str, indent: str = "\t") -> None:
    lines.append(f"{indent}{header} = {{")
    for raw_line in body.strip().splitlines():
        lines.append(f"{indent}\t{raw_line.rstrip()}")
    lines.append(f"{indent}}}")


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def create_interaction(
        interaction_id: str,
        display_name: str,
        description: str,
        is_shown: str,
        on_accept: str,
        is_valid: Optional[str] = None,
        category: str = "interaction_category_friendly",
        interface_priority: int = 50,
        auto_accept: bool = False,
        ai_accept_base: int = 0,
        on_decline: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 character interaction definition and localization entries.

        Args:
            interaction_id: Internal snake_case interaction identifier.
            display_name: Player-facing interaction name.
            description: Tooltip shown in interaction UI.
            is_shown: CK3 trigger block body controlling visibility.
            on_accept: CK3 effect block body executed when accepted.
            is_valid: Optional CK3 trigger block body for valid targets.
            category: Interaction category key (e.g. interaction_category_friendly).
            interface_priority: UI ordering priority.
            auto_accept: If True, interaction auto-accepts where valid.
            ai_accept_base: Base AI acceptance score.
            on_decline: Optional CK3 effect block body for decline case.
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to the generated interaction and localization files.
        """
        base = output_dir / (mod_name or "mod")
        interactions_dir = base / "common" / "character_interactions"
        loc_dir = base / "localization" / "english"
        interactions_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"{interaction_id} = {{"]
        lines.append(f"\tcategory = {category}")
        lines.append(f"\tinterface_priority = {interface_priority}")
        lines.append(f"\tdesc = {interaction_id}_desc")
        lines.append(f"\tauto_accept = {'yes' if auto_accept else 'no'}")
        lines.append("\tai_accept = {")
        lines.append(f"\t\tbase = {ai_accept_base}")
        lines.append("\t}")

        _emit_block(lines, "is_shown", is_shown)

        if is_valid:
            _emit_block(lines, "is_valid", is_valid)

        _emit_block(lines, "on_accept", on_accept)

        if on_decline:
            _emit_block(lines, "on_decline", on_decline)

        lines.append("}")

        interaction_path = interactions_dir / f"{interaction_id}.txt"
        interaction_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        loc_content = (
            "l_english:\n"
            f' {interaction_id}:0 "{display_name}"\n'
            f' {interaction_id}_desc:0 "{description}"\n'
        )
        loc_path = loc_dir / f"{interaction_id}_l_english.yml"
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return f"Interaction:  {interaction_path}\nLocalization: {loc_path}"

    @mcp.tool()
    def create_event(
        namespace: str,
        event_number: int,
        display_title: str,
        description: str,
        trigger: str,
        event_type: str = "character_event",
        immediate: Optional[str] = None,
        option_text: str = "Continue",
        option_effect: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 event definition and localization entries.

        Args:
            namespace: Event namespace (e.g. 'wizard_study_lore').
            event_number: Numeric event id within the namespace.
            display_title: Player-facing event title.
            description: Event description text.
            trigger: CK3 trigger block body for the event.
            event_type: CK3 event type key (default: character_event).
            immediate: Optional CK3 effect block body run on fire.
            option_text: Button text for the primary option.
            option_effect: Optional CK3 effect block body for the primary option.
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to the generated event and localization files.
        """
        base = output_dir / (mod_name or "mod")
        events_dir = base / "events"
        loc_dir = base / "localization" / "english"
        events_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        full_id = f"{namespace}.{int(event_number)}"
        title_key = f"{full_id}.t"
        desc_key = f"{full_id}.desc"
        option_key = f"{full_id}.a"

        lines = [f"namespace = {namespace}", "", f"{full_id} = {{"]
        lines.append(f"\ttype = {event_type}")
        lines.append(f"\ttitle = {title_key}")
        lines.append(f"\tdesc = {desc_key}")
        _emit_block(lines, "trigger", trigger)

        if immediate:
            _emit_block(lines, "immediate", immediate)

        lines.append("\toption = {")
        lines.append(f"\t\tname = {option_key}")
        if option_effect:
            for raw_line in option_effect.strip().splitlines():
                lines.append(f"\t\t{raw_line.rstrip()}")
        lines.append("\t}")
        lines.append("}")

        event_path = events_dir / f"{namespace}_{int(event_number)}.txt"
        event_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        loc_content = (
            "l_english:\n"
            f' {title_key}:0 "{display_title}"\n'
            f' {desc_key}:0 "{description}"\n'
            f' {option_key}:0 "{option_text}"\n'
        )
        loc_path = loc_dir / f"{namespace}_{int(event_number)}_l_english.yml"
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return f"Event:        {event_path}\nLocalization: {loc_path}"

    @mcp.tool()
    def create_interaction_event_chain(
        interaction_id: str,
        display_name: str,
        description: str,
        is_shown: str,
        event_namespace: str,
        request_event_title: str,
        request_event_desc: str,
        completion_event_title: str,
        completion_event_desc: str,
        is_valid: Optional[str] = None,
        on_accept_effect: Optional[str] = None,
        request_event_number: int = 1001,
        completion_event_number: int = 1002,
        chain_delay_months: int = 6,
        category: str = "interaction_category_friendly",
        interface_priority: int = 50,
        auto_accept: bool = False,
        ai_accept_base: int = 0,
        request_option_text: str = "Begin",
        completion_option_text: str = "Continue",
        request_option_effect: Optional[str] = None,
        completion_option_effect: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 interaction plus a two-step follow-up event chain.

        This helper is intended for mentorship/study flows where accepting an
        interaction starts an event immediately and a completion event later.

        Args:
            interaction_id: Internal snake_case interaction identifier.
            display_name: Player-facing interaction name.
            description: Interaction tooltip text.
            is_shown: CK3 trigger body for interaction visibility.
            event_namespace: Namespace for generated events.
            request_event_title: Title text for the first event.
            request_event_desc: Description text for the first event.
            completion_event_title: Title text for completion event.
            completion_event_desc: Description text for completion event.
            is_valid: Optional CK3 trigger body for valid targets.
            on_accept_effect: Optional extra effects in interaction on_accept.
            request_event_number: Numeric id for first event.
            completion_event_number: Numeric id for completion event.
            chain_delay_months: Delay before completion event fires.
            category: Interaction category key.
            interface_priority: UI ordering priority.
            auto_accept: If True, interaction auto-accepts where valid.
            ai_accept_base: Base AI acceptance score.
            request_option_text: Button text for first event option.
            completion_option_text: Button text for completion event option.
            request_option_effect: Optional effects for first event option.
            completion_option_effect: Optional effects for completion option.
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to generated interaction/events/localization files.
        """
        base = output_dir / (mod_name or "mod")
        interactions_dir = base / "common" / "character_interactions"
        events_dir = base / "events"
        loc_dir = base / "localization" / "english"
        interactions_dir.mkdir(parents=True, exist_ok=True)
        events_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        request_id = f"{event_namespace}.{int(request_event_number)}"
        completion_id = f"{event_namespace}.{int(completion_event_number)}"
        delay_days = max(1, int(chain_delay_months)) * 30

        interaction_lines = [f"{interaction_id} = {{"]
        interaction_lines.append(f"\tcategory = {category}")
        interaction_lines.append(f"\tinterface_priority = {interface_priority}")
        interaction_lines.append(f"\tdesc = {interaction_id}_desc")
        interaction_lines.append(f"\tauto_accept = {'yes' if auto_accept else 'no'}")
        interaction_lines.append("\tai_accept = {")
        interaction_lines.append(f"\t\tbase = {ai_accept_base}")
        interaction_lines.append("\t}")
        _emit_block(interaction_lines, "is_shown", is_shown)
        if is_valid:
            _emit_block(interaction_lines, "is_valid", is_valid)
        interaction_lines.append("\ton_accept = {")
        interaction_lines.append(f"\t\ttrigger_event = {request_id}")
        if on_accept_effect:
            for raw_line in on_accept_effect.strip().splitlines():
                interaction_lines.append(f"\t\t{raw_line.rstrip()}")
        interaction_lines.append("\t}")
        interaction_lines.append("}")

        interaction_path = interactions_dir / f"{interaction_id}.txt"
        interaction_path.write_text("\n".join(interaction_lines) + "\n", encoding="utf-8")

        req_title_key = f"{request_id}.t"
        req_desc_key = f"{request_id}.desc"
        req_opt_key = f"{request_id}.a"
        done_title_key = f"{completion_id}.t"
        done_desc_key = f"{completion_id}.desc"
        done_opt_key = f"{completion_id}.a"

        event_lines = [f"namespace = {event_namespace}", "", f"{request_id} = {{"]
        event_lines.append("\ttype = character_event")
        event_lines.append(f"\ttitle = {req_title_key}")
        event_lines.append(f"\tdesc = {req_desc_key}")
        event_lines.append("\toption = {")
        event_lines.append(f"\t\tname = {req_opt_key}")
        if request_option_effect:
            for raw_line in request_option_effect.strip().splitlines():
                event_lines.append(f"\t\t{raw_line.rstrip()}")
        event_lines.append(f"\t\ttrigger_event = {{ id = {completion_id} days = {delay_days} }}")
        event_lines.append("\t}")
        event_lines.append("}")
        event_lines.append("")
        event_lines.append(f"{completion_id} = {{")
        event_lines.append("\ttype = character_event")
        event_lines.append(f"\ttitle = {done_title_key}")
        event_lines.append(f"\tdesc = {done_desc_key}")
        event_lines.append("\toption = {")
        event_lines.append(f"\t\tname = {done_opt_key}")
        if completion_option_effect:
            for raw_line in completion_option_effect.strip().splitlines():
                event_lines.append(f"\t\t{raw_line.rstrip()}")
        event_lines.append("\t}")
        event_lines.append("}")

        event_path = events_dir / f"{event_namespace}_chain.txt"
        event_path.write_text("\n".join(event_lines) + "\n", encoding="utf-8")

        loc_content = (
            "l_english:\n"
            f' {interaction_id}:0 "{display_name}"\n'
            f' {interaction_id}_desc:0 "{description}"\n'
            f' {req_title_key}:0 "{request_event_title}"\n'
            f' {req_desc_key}:0 "{request_event_desc}"\n'
            f' {req_opt_key}:0 "{request_option_text}"\n'
            f' {done_title_key}:0 "{completion_event_title}"\n'
            f' {done_desc_key}:0 "{completion_event_desc}"\n'
            f' {done_opt_key}:0 "{completion_option_text}"\n'
        )
        loc_path = loc_dir / f"{interaction_id}_chain_l_english.yml"
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return (
            f"Interaction:  {interaction_path}\n"
            f"Events:       {event_path}\n"
            f"Localization: {loc_path}"
        )
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


def get_tools(output_dir) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, output_dir)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
