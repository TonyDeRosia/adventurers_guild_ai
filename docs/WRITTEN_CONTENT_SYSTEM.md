# Written Content System

Phase 10A uses one canonical `WrittenContentService` for mail, letters, notes, books, journals, board posts, signs, plaques, and readable lore. Runtime authority is SQLite: document instances identify the object, immutable versions preserve content history, delivery/publication/read-state rows represent context, and audit rows record every mutation.

The system intentionally forbids external email, Discord/forum bridges, cross-server delivery, unrestricted HTML, executable links, JavaScript, file uploads, and AI-authored authority bypasses. Plain text is supported, safe semantic MUD markup can be allowed by sanitization profiles, and unsafe terminal control sequences are rejected.

Manual acceptance commands:

```text
mail compose <second player>
.subject Test Letter
.append This is a test message.
.preview
.send
mail inbox
mail read 1
board list
board post
.subject First Notice
.append Testing the public board.
.publish
board read 1
board reply 1
read guildlands guide
contents guildlands guide
read guildlands guide page 2
write journal
.append Today I arrived in Guildlands.
.save
```

Expected persistence: mailboxes, delivery records, document versions, read state, attachment claims, board threads, and book progress survive restart without duplicate delivery or duplicate item claim.
