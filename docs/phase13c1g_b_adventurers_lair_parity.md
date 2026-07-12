# Phase 13C1G-B Adventurer's Lair Parity Matrix

| Feature | Adventurer's Lair behavior | Smart MUD implementation | Visual match | Builder customizable | Accessibility behavior | Intentional difference | Automated test | Manual test |
|---|---|---|---|---|---|---|---|---|
| score identity | dense framed identity rows | structured score snapshot and framed rows | close | labels/frame/width | no-color/reduced-decoration | canonical labels may differ | focused display tests | score |
| score resources | colored HP/Mana/Stamina | semantic resource row | close | labels/roles | colors neutralized | no gameplay formula changes | focused display tests | score |
| score progression | XP/TNL rows | canonical progression rows | close | section metadata | content preserved | hidden unsupported fields omitted | focused display tests | score |
| score carrying | carry weight line | snapshot carrying line | partial | labels/width | wraps safely | package-specific wording differs | focused display tests | score |
| score attributes | compact columns | synchronized DisplayRow cells | close | width/frame | no clipping in narrow | formulas unchanged | wrapping tests | score narrow |
| score combat | combat stat rows | canonical calculated stats | close | section metadata | colors neutralized | missing values omitted | focused display tests | score combat |
| score currency | coin row | worth/score currency cells | close | labels/roles | colors neutralized | economy source canonical | worth tests | worth |
| score survival | hunger/thirst rows | survival snapshot rows | partial | section metadata | content preserved | unavailable values omitted | score tests | score |
| score effects | effects list | affects command unified frame | partial | labels/roles | positive/negative roles remapped | score may not inline every affect | affects tests | affects |
| score time | played/login rows | time snapshot rows | partial | section metadata | content preserved | wording differs | score tests | score |
| worth | coherent currency display | themed worth frame | close | title/roles/frame | no-color supported | not copied strings | worth tests | worth |
| skills | readable framed list | themed ability builder | close | title/frame/width | wraps safely | data from ability service | skills tests | skills |
| spells | readable framed list | themed ability builder | close | title/frame/width | wraps safely | data from spell service | spells tests | spells |
| abilities | active/passive list | themed ability builder | close | title/frame/width | wraps safely | canonical availability | abilities tests | abilities |
| cooldowns | status lines | themed cooldown list | partial | title/frame/width | wraps safely | service-backed rows | cooldown tests | cooldowns |
| affects | colored affects | themed affects frame | partial | title/roles/frame | roles neutralized | hidden affects stay hidden | affects tests | affects |
| inventory | grouped carried items | themed inventory frame | close | empty/title/frame | colors safe | grouping key differs | inventory tests | inventory |
| equipment | slot list | themed equipment frame | close | empty/title/frame | colors safe | no duplicate unless canonical state | equipment tests | equipment |
| prompt | configurable colors/tokens | prompt presets and player overrides | close | presets | no-color strips roles | token set differs | prompt tests | prompt |
| prompt tokens | `%` tokens | safe token replacement | close | preset text | colors neutralized | unsupported tokens warn | prompt tests | prompt |
| ANSI width | ANSI-aware wrapping | MUD/semantic/entity tokenizer | partial | n/a | n/a | token grammar differs | wrapping tests | narrow score |
| display themes | authored style files | validated DisplayTheme/ResolvedDisplayTheme | close | yes | accessibility wins | no raw code templates | display theme tests | display theme |
| world assignment | package default | resolver supports world default fields | partial | builder assign route | accessibility wins | lightweight persistence | validation tests | assign world |
| zone assignment | zone override | resolver contract supports zone field | partial | builder assign route | accessibility wins | content-model dependent | validation tests | assign zone |
| area assignment | area override | resolver contract supports area field | partial | builder assign route | accessibility wins | content-model dependent | validation tests | assign area |
| player preference | player style choice | persistent preferences service | close | player commands | accessibility wins | only selectable list shown | preference tests | display theme |
| Builder colors | authored ANSI freedom | safe MUD markup only | close | labels/prompts/items | no-color strips | raw ANSI rejected | security tests | displaytheme label |
