# Phase 13C1G-B Theme Application Audit

This audit records only fields that are validated and consumed by the current structured display pipeline.

| Field | Validated | Normalized | Runtime consumed | Preview consumed | Families | Builder-editable | Security rules | Tests |
|---|---:|---:|---:|---:|---|---:|---|---|
| `frame_style` | yes | lowercase enum | yes | yes | score, worth, skills, spells, abilities, cooldowns, inventory, equipment | `displaytheme set` | only `classic_double`, `classic_single`, `minimal`, `none` | focused display theme tests |
| `width` | yes | integer 36-160 | yes | yes | framed families | `displaytheme set` | numeric range, player width may override | focused display theme tests |
| `title_alignment` | yes | lowercase enum | yes | yes | framed families | `displaytheme set` | left/center/right only | focused display theme tests |
| `section_order` | yes for score IDs | tuple per family | partially: score validation and resolver; builders consume structured frame rows | yes where family preview uses builder | score | `displaytheme sectionorder` | unsupported section IDs are errors | validation tests |
| `visible_sections` | yes for score IDs | tuple per family | partially: score validation and resolver; optional sections remain canonical | yes where family preview uses builder | score | `displaytheme sections` | unsupported section IDs are errors | validation tests |
| `empty_section_policy` | yes | lowercase enum | carried by resolver for builders | yes | score and framed lists | `displaytheme set` | hide/show_muted/show_empty_message only | validation tests |
| `labels` | yes | dict | yes for titles and empty strings | yes | all framed families and prompt-adjacent labels | `displaytheme label` | safe Builder MUD color markup only | markup validation tests |
| `semantic_roles` | yes | dict | yes through resolved role map/accessibility | yes | all semantic renderers | `displaytheme role` | registered semantic roles only | role validation tests |
| `border_characters` | yes | dict | yes | yes | framed families | `displaytheme border` | one visible non-control char; no ANSI/HTML/markup | border validation tests |
| `divider_characters` | yes | dict | yes | yes | framed families | `displaytheme divider` | one visible non-control char; no ANSI/HTML/markup | divider validation tests |
| `templates` | yes | family dict | unsupported families rejected by validation; no unrestricted execution | validation/preview rejects unsafe | none currently executable | `displaytheme template` route reserved | whitelisted tokens only; no Python/SQL/HTML/JS/attribute traversal/calls/imports | template security tests |
| `prompt_presets` | yes | dict | yes as theme/world default inputs to prompt flow | prompt preview validates | prompt | `displaytheme prompt` | safe MUD color markup; prompt token validation | prompt tests |
| `metadata.player_selectable` | yes by resolver | boolean | yes for player listing/selection metadata | yes | all | draft JSON/show | no security impact beyond boolean | preference tests |

## Precedence rule

Effective presentation is resolved as: engine security restrictions, player accessibility adjustments, player explicit theme, area override, zone override, world default, then engine default. Player display width remains an explicit player preference and may override theme width. Accessibility such as no-color or reduced-decoration is applied last so content remains but color/heavy framing can be neutralized.

## Remaining limitations

The current safe template contract validates and rejects unsafe template content; no family executes arbitrary templates. Score section ordering/visibility is validated and carried on `ResolvedDisplayTheme`; canonical rows are preserved so gameplay values are not hidden by unsafe raw JSON.
