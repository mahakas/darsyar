# Phase 6: Chat UI & Accessible Multilingual Experience

**Status:** Partial UI/chat prototype exists; Phase remains Planned and is not accepted.  
**Dependencies:** Phases 1, 3 and 5

## Implemented prototype

- React/TypeScript application shell with basic fa/en/ar language switching and RTL/LTR direction.
- Initial chat composer with grade selection, fetch-based SSE streaming and stop/abort control.
- Basic API client and stream parsing helpers.

The current prototype is not a complete authenticated student experience and does not yet expose the full evidence, history and accessibility contract.

## Remaining work

- [ ] Integrate frontend authentication/session lifecycle with backend OTP and refresh-cookie/CSRF contracts.
- [ ] Fetch-based streaming client with robust reconnect/replay, sequence handling and partial-response status.
- [ ] Conversation history/pagination and user-visible search/navigation.
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
