# docs.plus

## What the driver runs

`build/score_all.py` measures docs.plus from `out/docsplus`. `build/run_all.sh` runs `harness/docsplus/roundtrip.ts` with Bun. This note does not publish a new round-trip percentage for that output.

## What it is

docs.plus is a real-time collaborative document editor. The DOCX round trip in this benchmark is a headless pass through its Tiptap document, not the multi-user site.

## Trivia

The license is MIT, copyright 2023–2026 Hossein Marzban. The README's structural idea is that every heading has its own chatroom, and the table of contents shows who is in it. The runtime is Bun. The web app is Next.js and Tiptap. An MCP path lets Claude or ChatGPT read documents the account can open and edit documents the account owns. The site is docs.plus.
