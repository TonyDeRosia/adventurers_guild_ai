from __future__ import annotations
import re, textwrap
from typing import Any, Sequence
ANSI_RE=re.compile(r"\x1b\[[0-9;]*m")
def strip_ansi(s:str)->str: return ANSI_RE.sub('', str(s))
def visible_len(s:str)->int: return len(strip_ansi(s))
def _fmt_flag(s:str)->str: return str(s).upper().replace('_','-')
def _join(vals, nobits='NOBITS'):
    vals=[_fmt_flag(v) for v in (vals or []) if str(v)]
    return ' '.join(vals) if vals else nobits
def _title(v): return str(v or '').replace('_',' ').title()
def _id_line(rec:dict[str,Any], oid:str)->str:
    v=rec.get('vnum') or rec.get('legacy_vnum')
    if v is not None and str(v)!='': return f"-- Mob Number: [{v}] ID: [{oid}]"
    return f"-- Mob ID: [{oid}]"
def _wrap(text:str,width:int=79,indent:str=''):
    cap=max(40,min(int(width or 79),90)); out=[]
    for para in str(text or '').splitlines() or ['']:
        if not para: out.append(''); continue
        out += textwrap.wrap(para,width=cap,initial_indent=indent,subsequent_indent='',replace_whitespace=False) or ['']
    return out
def render_medit_main(sess,width:int=79)->str:
    r=sess.working_record or {}; cp=r.get('combat_profile') or {}
    kw=' '.join(r.get('keywords') or r.get('aliases') or []) or '(none)'
    sdesc=r.get('short_description') or r.get('name') or ''
    ldesc=r.get('room_description') or r.get('long_description') or r.get('description') or ''
    ddesc=r.get('look_description') or r.get('examine_description') or ''
    flags=r.get('mobile_flags') or r.get('flags') or []
    aff=r.get('affect_flags') or []
    scripts=r.get('script_attachments') or r.get('script_ids') or r.get('scripts') or []
    sc='Not Set.' if not scripts else f"{len(scripts)} attached"
    pet=r.get('pet_price', None); pet='(default)' if pet in (None,'') else ('Disabled' if str(pet)=='0' else str(pet))
    lines=[_id_line(r,sess.object_id),'']
    line1=f"1) Sex: {r.get('sex') or 'unknown'}"
    lines.append(f"{line1:<30}2) Keywords: {kw}")
    lines.append(f"3) S-Desc: {sdesc}")
    lines.append('4) L-Desc:-'); lines += _wrap(ldesc,width); lines.append('')
    lines.append('5) D-Desc:-'); lines += _wrap(ddesc,width,'   '); lines.append('')
    lines += [
        f"6) Position  : {_title(r.get('spawn_position') or r.get('position') or 'standing')}",
        f"7) Default   : {_title(r.get('default_position') or 'standing')}",
        f"8) Attack    : {cp.get('attack_type') or r.get('attack_type') or 'fist'}",
        "9) Stats Menu...",
        "I) Identity / Traits",
        f"A) NPC Flags : {_join(flags)}",
        f"B) AFF Flags : {_join(aff)}",
        f"P) Pet Price : {pet}",
        "R) Loadout / Loot",
        f"S) Script    : {sc}",
        "U) Combat Abilities",
        "V) Event Reactions",
        "W) Copy mob",
        "X) Delete mob",
        "Q) Quit",
        "Enter choice :",
    ]
    return '\n'.join(lines)
def _columns(flags:Sequence[str], width:int, want:int)->list[str]:
    width=int(width or 79); names=[_fmt_flag(f) for f in flags]
    if not names: return []
    cols=want
    maxcell=max(len(f"{i}) {n}") for i,n in enumerate(names,1))+2
    while cols>1 and cols*maxcell>width: cols-=1
    rows=(len(names)+cols-1)//cols; out=[]
    for row in range(rows):
        parts=[]
        for c in range(cols):
            i=row+c*rows
            if i<len(names): parts.append(f"{i+1}) {names[i]}".ljust(maxcell))
        out.append(''.join(parts).rstrip())
    return out
def render_medit_flags(sess, field:str, flags:Sequence[str], width:int=79)->str:
    cur=sess.working_record.get(field) or []
    title='mob' if field=='mobile_flags' else 'aff'
    want=2 if field=='mobile_flags' else 4
    lines=_columns(flags,width,want)
    lines += ['', f"Current flags : {_join(cur)}", f"Enter {title} flags (0 to quit) :"]
    return '\n'.join(lines)
def render_medit_identity(sess)->str:
    r=sess.working_record or {}; name=r.get('name') or sess.object_id
    lines=[f"-- Mob Identity / Traits: [{r.get('vnum') or sess.object_id}] {name}",'',
    f"1) Name           : {name}",f"2) Stable ID      : {sess.object_id}",f"3) Legacy VNUM    : {r.get('vnum','')}",f"4) Species        : {r.get('species') or r.get('race') or 'unset'}",f"5) Classification : {r.get('classification') or r.get('entity_type') or 'npc'}",f"6) Size           : {r.get('size') or 'medium'}",f"7) NPC Role       : {r.get('npc_role') or r.get('occupation') or r.get('behavior_profile_id') or 'unset'}",f"8) Enabled        : {'Yes' if r.get('enabled', True) else 'No'}",f"9) Builder Tags   : {', '.join(r.get('tags') or []) or 'none'}","Q) Quit to main menu","Enter choice :"]
    return '\n'.join(lines)
def render_medit_stats(sess)->str:
    r=sess.working_record or {}; a=r.get('attributes') or {}; res=r.get('resources') or {}; cp=r.get('combat_profile') or {}; sep='-'*78
    hp=((res.get('health') or {}).get('maximum') if isinstance(res.get('health'),dict) else res.get('health')) or 0
    dmg=cp.get('damage_dice') or r.get('damage_dice') or '1d2'
    lines=[sep,f"MOB BUILD: [{r.get('vnum') or sess.object_id}] {r.get('name') or sess.object_id}",sep,'QUICK BUILD',f"(1) Level:                         [{int(r.get('level') or 1):5d}]",'(2) Reapply Recommended Stats','', 'Tip: Set the level first.','     After changing level, accept the Y/N prompt to fill recommended stats.','     Use option 2 later to refresh recommended values again.',sep,'HIT POINTS',f"(3) Health Maximum:                [{int(hp):5d}]",f"    HP Preview:                    [{int(hp):5d}]",sep,'DAMAGE',f"(6) Damage Dice:                   [{dmg:>8}]",f"(8) Damroll:                       [{int(cp.get('damroll') or cp.get('damage_bonus') or 0):5d}]",sep,'COMBAT',f"(A) Armor:                         [{int(cp.get('armor') or r.get('armor') or 0):5d}]",f"(B) Hitroll:                       [{int(cp.get('hitroll') or cp.get('accuracy') or 0):5d}]",f"(C) Evasion:                       [{int(cp.get('evasion') or 0):5d}]",f"(D) Alignment:                     [{int(r.get('alignment') or 0) if str(r.get('alignment') or '0').lstrip('-').isdigit() else str(r.get('alignment')):>5}]",sep,'ATTRIBUTES',f"(H) Str: [{int(a.get('strength') or 11):2d}]    (I) Int: [{int(a.get('intelligence') or 11):2d}]    (J) Wis: [{int(a.get('wisdom') or 11):2d}]",f"(K) Dex: [{int(a.get('dexterity') or 11):2d}]    (L) Con: [{int(a.get('constitution') or 11):2d}]    (M) Cha: [{int(a.get('charisma') or 11):2d}]",sep,'(Q) Quit to main menu','Enter choice :']
    return '\n'.join(lines)
def render_simple_list(sess, key, title):
    entries=sess.working_record.get(key) or []; lines=[f"{title} ({len(entries)}/10)",'']
    if not entries: lines.append('   [NONE]')
    else:
        for i,e in enumerate(entries,1): lines.append(f"{i}) {e.get('ability_id') or e.get('event_type') or e.get('script_id') or e.get('id')} -> {e.get('action_type') or e.get('trigger') or ''}")
    lines += ['', 'A) Add   E) Edit   D) Delete   T) Toggle   Q) Quit','Enter choice:']
    return '\n'.join(lines)
def render_loadout(sess):
    r=sess.working_record or {}; l=r.get('equipment_loadout') or {}; eq=len(l.get('equipped') or {}) if isinstance(l,dict) else 0; inv=len(l.get('carried') or r.get('starting_inventory') or []) if isinstance(l,dict) else 0; loot=len((r.get('loot') or {}).get('entries') or []) if isinstance(r.get('loot'),dict) else 0
    return f"-- Loadout / Loot: [{r.get('vnum') or sess.object_id}] {r.get('name') or sess.object_id}\n\nE) Equipment       : {eq} entries\nI) Inventory       : {inv} entries\nL) Loot / Corpse   : {loot} entries\nQ) Quit to main menu\nEnter choice :"
def render_scripts(sess):
    r=sess.working_record or {}; scripts=r.get('script_attachments') or r.get('script_ids') or r.get('scripts') or []
    lines=[f"-- Scripts: [{r.get('vnum') or sess.object_id}] {r.get('name') or sess.object_id}",'']
    lines += [f"{i}) [{s.get('script_id') if isinstance(s,dict) else s}]" for i,s in enumerate(scripts,1)] or ['   [NONE]']
    lines += ['','A) Add   D) Delete   V) View   Q) Quit','Enter choice :']
    return '\n'.join(lines)
