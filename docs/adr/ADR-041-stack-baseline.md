# ADR-041: خط پایهٔ نسخه‌های فناوری

- Status: proposed
- Context: نسخه‌های جدید باید با wheelها، imageها و ابزار CI سازگار باشند.
- Decision: targetهای AGENTS v4 مبنا هستند؛ هیچ lockfile دستی ساخته نمی‌شود. major downgrade/upgrade با ADR؛ patch امنیتی با تست.
- Rejected alternatives: `latest` و نصب شناور در CI.
- Consequences: `uv.lock` و `package-lock.json` باید در فاز صفر با registry واقعی ساخته شوند.
- Affected files: `docs/TECH_STACK.md`, `backend/pyproject.toml`, `frontend/package.json`, CI.
