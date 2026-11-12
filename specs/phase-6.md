# Phase 6: Chat UI & Accessible Multilingual Experience

**Status:** Partial — authenticated profile/session, server-authoritative grade, owner-scoped conversation/message history and searchable pagination merged on 2026-11-12. Phase remains Partial and is not accepted.  
**Dependencies:** Phases 1, 3 and 5

## Implemented prototype

- React/TypeScript application shell with basic fa/en/ar language switching and RTL/LTR direction.
- Initial chat composer with grade selection, fetch-based SSE streaming and stop/abort control.
- Basic API client and stream parsing helpers.

The current prototype is not a complete authenticated student experience and does not yet expose the full evidence, history and accessibility contract.

## Implemented in repository (verified 2026-11-12)

- Authenticated frontend session restoration and sign-out are connected to the backend OTP/refresh-cookie lifecycle.
- Student grade is explicitly selected and persisted; there is no client-controlled grade ceiling or fallback grade in chat.
- Conversation listing and message history are owner-scoped, bounded/paginated, and omit provider/internal billing identifiers.
- Conversation search is server-side and title-based; new chats receive a bounded title from the first user prompt.
- Message status history distinguishes completed, partial, failed, cancelled and streaming states.
- New-chat preflight is read-only; sequential idempotent retries reuse the persisted conversation and reservation.
- The sidebar provides conversation search/navigation and older-conversation pagination; chat history loads additional message pages.
- Main CI after merge: backend 481 passed / 21 skipped / 1 warning; frontend lint/typecheck/build PASS; Linux SIGTERM PASS (Run 43126829480).

These are implemented capabilities, not phase acceptance. They do not establish the RAG/evidence, accessibility or full visual acceptance criteria below.

## Remaining work

- [x] Integrate frontend authentication/session lifecycle with backend OTP and refresh-cookie/CSRF contracts.
- [ ] Fetch-based streaming client with robust reconnect/replay, sequence handling and partial-response status.
- [x] Conversation history/pagination and user-visible search/navigation.
- [ ] Evidence SourceCard and citation detail panel backed by request evidence, not model-authored citation text.
- [ ] Safe Markdown rendering; KaTeX with trust=false; Mermaid strict/sandbox policy.
- [ ] fa/en/ar with direction-aware logical CSS properties; test RTL/LTR and responsive desktop/tablet/mobile layouts.
- [ ] Theme preferences, keyboard/screen-reader usability and user-visible web-source distinction.
- [ ] XSS and citation-display tests; user-safe API errors without stack or sensitive data.

## Goal

Turn the shell into a complete, responsive educational chat experience.

## Out of scope

- Unsupported/private teacher and learning tools in MVP

## Acceptance criteria

- [ ] Keyboard/screen-reader usability checks pass.
- [ ] RTL/LTR tested across languages.
- [ ] XSS and citation display tests pass.
- [ ] API errors surfaced without stack or sensitive data.

## Required evidence

- Commands actually executed, exit code and important output.
- Files changed and references to applicable `R-NNN` rules.
- Risks, assumptions, and `NOT RUN` checks with exact blocker.
- New decisions in an ADR before code when required.
