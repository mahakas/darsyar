# ADR-005: استناد سمت سرور

- Status: Accepted
- Decision: مدل فقط شناسه/متن شواهد را از context می‌بیند؛ سرور citation را از evidenceهای واقعی و معتبر تولید می‌کند.
- Required checks: evidence belongs to query scope, grade <= selected grade, source edition valid, page known or `-`, no duplicate citations.
- Consequences: prompt instructions به‌تنهایی معیار اعتبار citation نیستند؛ API باید evidence ids را اعتبارسنجی و render کند.
