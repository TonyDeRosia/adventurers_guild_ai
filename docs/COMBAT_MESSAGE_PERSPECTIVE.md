# Combat Message Perspective (Phase 15B.12)

Combat messages are audience-specific: attacker, victim, and observer strings are selected independently. Severity text is placed by the template so invalid ordering such as `punches hard you` is not emitted.

Condition transitions are also audience-specific. A player whose health crosses a band receives second-person text such as `You look wounded.` or `You are badly injured.` Other occupants receive third-person observer text such as `Kraevok looks wounded.`

Condition messages are only emitted when a defender crosses to a new condition band; ordinary HP changes within the same band do not repeat the transition line.
