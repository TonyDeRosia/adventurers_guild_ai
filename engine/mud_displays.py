"""Smart MUD display rendering engine with semantic color roles."""

from __future__ import annotations

from typing import Any, Optional
import html


def render_room(room: Any, colors: dict[str, str], character: Any = None) -> str:
    """Render room description with inline exits using semantic roles."""
    lines = []
    
    # Room area and title
    if hasattr(room, 'area_id') and room.area_id:
        lines.append(f'<span role="area_name">{html.escape(room.area_id)}</span>')
    
    lines.append(f'<span role="room_name">{html.escape(room.title if hasattr(room, "title") else "Unknown Room")}</span>')
    
    # Description
    desc = room.description if hasattr(room, 'description') else ""
    if desc:
        lines.append(f'<span role="room_description">{html.escape(desc)}</span>')
    
    # Inline exits (classic MUD style)
    exits = getattr(room, 'exits', [])
    if exits:
        exit_names = []
        if isinstance(exits, list):
            for exit_def in exits:
                if isinstance(exit_def, dict):
                    direction = exit_def.get('direction', exit_def.get('dir', ''))
                else:
                    direction = str(exit_def)
                if direction:
                    exit_names.append(direction)
        
        if exit_names:
            exit_str = "[ Exits: " + " ".join(
                f'<span role="exit">{html.escape(e)}</span>' for e in exit_names
            ) + " ]"
            lines.append(exit_str)
    else:
        lines.append('<span role="exit">[ Exits: none ]</span>')
    
    visible: list[str] = []
    for npc in getattr(room, "npcs", []) or []:
        if isinstance(npc, dict):
            text = npc.get("room_description") or npc.get("description") or npc.get("name") or npc.get("id")
        else:
            text = str(npc)
        if text:
            visible.append(f'<span role="npc">{html.escape(str(text))}</span>')

    for obj in getattr(room, "objects", []) or []:
        if isinstance(obj, dict):
            text = obj.get("room_description") or obj.get("description") or obj.get("name") or obj.get("id")
        else:
            text = str(obj)
        if text:
            visible.append(f'<span role="object">{html.escape(str(text))}</span>')

    if visible:
        lines.append('<span role="system">You see:</span>')
        lines.extend(f"  {entry}" for entry in visible)
    
    print("[mud-render] Room rendered")
    return "\n".join(lines)


def render_prompt(character: Any, colors: dict[str, str]) -> str:
    """Render MUD prompt with semantic color roles."""
    # Minimal classic MUD prompt style
    prompt = (
        f'<span role="prompt_marker">&gt;</span> '
        f'<span role="prompt_hp">{character.name}</span> '
        f'<span role="score_label">HP:</span> <span role="prompt_hp">{character.hp}/{character.max_hp}</span> '
    )
    
    # Add mana if > 0
    if character.max_mana > 0:
        prompt += (
            f'<span role="score_label">MP:</span> <span role="prompt_mana">{character.mana}/{character.max_mana}</span> '
        )
    
    print("[mud-render] Prompt rendered")
    return prompt


def render_scrollback_line(output: str, role: str = "default", colors: dict[str, str] = None) -> str:
    """Render a single scrollback line with semantic role."""
    if colors is None:
        colors = {}
    
    return f'<span role="{html.escape(role)}">{html.escape(output)}</span>'


def render_command_echo(command: str, colors: dict[str, str]) -> str:
    """Render echoed command input."""
    return f'<span role="command_echo">&gt; {html.escape(command)}</span>'


def render_system_message(message: str, message_type: str = "system") -> str:
    """Render system message with appropriate role."""
    roles = {
        "system": "system",
        "error": "error",
        "warning": "warning",
        "combat": "combat",
        "quest": "quest",
    }
    role = roles.get(message_type, "system")
    return f'<span role="{role}">{html.escape(message)}</span>'


def render_combat_output(attacker: str, action: str, target: str, damage: int = 0, 
                        hit: bool = True, colors: dict[str, str] = None) -> str:
    """Render combat action output."""
    if colors is None:
        colors = {}
    
    if hit:
        return (
            f'<span role="combat">{html.escape(attacker)}</span> '
            f'<span role="combat">{html.escape(action)}</span> '
            f'<span role="combat">{html.escape(target)}</span> '
            f'<span role="damage">for {damage} damage</span>.'
        )
    else:
        return (
            f'<span role="combat">{html.escape(attacker)}</span> '
            f'<span role="combat">{html.escape(action)}</span> '
            f'<span role="warning">but misses</span> '
            f'<span role="combat">{html.escape(target)}</span>.'
        )


def render_dialogue(speaker: str, text: str, speaker_role: str = "npc") -> str:
    """Render dialogue with speaker color role."""
    role_colors = {
        "npc": "npc",
        "mob": "mob",
        "player": "player",
    }
    role = role_colors.get(speaker_role, "dialogue")
    
    return (
        f'<span role="{role}">{html.escape(speaker)}</span> '
        f'<span role="dialogue">says: "{html.escape(text)}"</span>'
    )


def render_inventory_list(character: Any, colors: dict[str, str]) -> str:
    """Render inventory display."""
    if not character.inventory:
        return '<span role="system">You are not carrying anything.</span>'
    
    lines = ['<span role="system">You are carrying:</span>']
    for item in character.inventory:
        item_name = item.get('name', 'unknown')
        qty = item.get('quantity', 1)
        rarity = item.get('rarity', 'common')
        role = f"item_{rarity}"
        
        qty_str = f" x{qty}" if qty > 1 else ""
        lines.append(f'  <span role="{role}">{html.escape(item_name)}</span>{qty_str}')
    
    return '\n'.join(lines)


def render_equipment_list(character: Any, colors: dict[str, str]) -> str:
    """Render equipment display."""
    if not character.equipment:
        return '<span role="system">You are not wearing anything.</span>'
    
    lines = ['<span role="system">You are wearing:</span>']
    for slot, item in character.equipment.items():
        item_name = item.get('name', 'empty') if item else 'empty'
        lines.append(
            f'  <span role="equipment_slot">{html.escape(slot)}</span>: '
            f'<span role="equipment_item">{html.escape(item_name)}</span>'
        )
    
    return '\n'.join(lines)


def apply_css_variables(colors: dict[str, str]) -> dict[str, str]:
    """Convert color roles to CSS variables for frontend application."""
    css_vars = {}
    for role, hex_color in colors.items():
        css_var_name = f"--mud-{role}"
        css_vars[css_var_name] = hex_color
    
    print(f"[mud-render] Generated {len(css_vars)} CSS variables")
    return css_vars
