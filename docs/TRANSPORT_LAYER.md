# Smart MUD Transport Layer

Smart MUD transports exist to keep the engine independent from any single client. The engine core (`MudRuntime`, command parser, SQLite state, world packages, plugins, and render helpers) remains authoritative. Transport adapters only manage connection lifecycle, input/output, session metadata, and output format negotiation.

## Shared concepts

`smart_mud.transport` defines:

- `TransportSession`: session id, transport type, remote address, optional account/character/world ids, timestamps, and capabilities.
- `TransportMessage`: a line or message from one session.
- `TransportResponse`: rendered output, prompt, output format, and metadata.
- `TransportAdapter`: the protocol implemented by client transports.

Supported output formats are `web_html`, `ansi_text`, and `plain_text`.

## Web transport

The built-in desktop/browser UI remains the primary Smart MUD experience. Web input flows through `WebTransportAdapter`, which delegates command execution to `MudRuntime.handle_input` and preserves web-safe HTML rendering for the existing UI.

The custom UI is kept because it can expose Smart MUD-specific settings, package/world selection, builder-oriented panels, and future desktop features that traditional telnet clients cannot provide.

## Telnet transport

`smart_mud.telnet_server` provides a plain TCP telnet-style foundation. It is disabled by default and can be enabled by configuration. It supports a welcome banner, temporary character-name prompt, line-based commands, ANSI/plain text output, disconnect handling, and clean shutdown.

A Mudlet, MUSHclient, TinTin, or raw telnet user would connect to the configured host and port, defaulting to port `4000` when enabled:

```text
telnet 127.0.0.1 4000
```

The initial flow is intentionally temporary:

```text
Welcome to Smart MUD.
Account system is not implemented yet.
Enter a temporary character name:
```

Full account authentication and multiplayer are not part of Phase 2A.

## Future websocket support

A websocket transport can implement the same adapter protocol. It should create `TransportSession` objects, forward input through `MudRuntime`, and select either semantic JSON/web HTML or plain text depending on client capability.

## Client support strategy

Telnet clients are supported because MUD players expect Mudlet, MUSHclient, TinTin, and raw telnet compatibility. They are not required: Smart MUD continues to ship its custom web desktop client as the richest interface.

## EventBus Integration

Transport adapters share the active `MudRuntime.event_bus`. Session creation publishes `transport_session_created`; inbound input publishes `transport_message_received`; generated responses publish `transport_response_sent`. Payloads include session id, transport type, output format, world/character ids when known, and command text where relevant. The transport layer remains a routing/presentation boundary and does not execute game side effects outside `MudRuntime`.
