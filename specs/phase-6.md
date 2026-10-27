# Phase 6: Chat UI & Accessible Multilingual Experience

**Status:** Planned  
**Dependencies:** Phases 1, 3 and 5

## Goal

Turn the shell into a complete, responsive educational chat experience.

## In scope

- [ ] Fetch streaming client, abort/reconnect, partial response status.
- [ ] Conversation history/pagination, evidence SourceCard and citation detail panel.
- [ ] Safe markdown, KaTeX trust=false, Mermaid strict/sandbox policy.
- [ ] fa/en/ar with dir and logical CSS properties; accessibility responsive desktop/mobile.
- [ ] Theme, grade selection and user-visible web-source distinction.

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
