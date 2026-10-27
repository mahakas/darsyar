# ADR-010: فیلتر سخت پایهٔ تحصیلی

- Status: Accepted
- Decision: `grade_level <= selected_grade` در query پایگاه داده و قبل از ranking اعمال می‌شود.
- Additional restrictions: tenant/user ACLs، document publication status، subject scope و edition policy هم قبل از ارائهٔ evidence اعمال شوند.
- Required tests: student grade 4 never retrieves evidence with grade 5+, including lexical, vector, reranker cache and web fallback.
