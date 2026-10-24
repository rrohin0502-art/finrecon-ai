# Contributing to FinRecon-AI

Thank you for your interest in contributing to FinRecon-AI! We are committed to maintaining a robust, auditable, and production-grade codebase for financial engineering.

---

## Code of Conduct

All contributors are expected to uphold a professional, respectful, and collaborative environment.

---

## Development Workflow

1. **Fork & Branch:** Create a feature branch off `main` (`feature/your-feature-name` or `fix/issue-description`).
2. **Environment Setup:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Coding Standards:**
   - Follow **PEP 8** style conventions.
   - Use strict type annotations (`typing` and `pydantic`).
   - Use `Decimal` or rounded floats for financial currency calculations. Never truncate cents without explicit rounding tolerance.
   - Write comprehensive unit tests for every new matching rule or anomaly heuristic.
4. **Testing:**
   Ensure all tests pass before opening a Pull Request:
   ```bash
   python -m tests.run_all_tests
   ```
5. **Pull Request:** Provide a clear description of the business rationale, test coverage, and performance impact.

---

## Adding New Reconciliation Rules

If you are proposing a new matching pass (e.g., FX triangulated cross-currency matching):
1. Document the mathematical formulation and false-positive risk in `docs/RECONCILIATION_RULES.md`.
2. Implement the rule as an isolated module in `finrecon/engine/`.
3. Add corresponding test fixtures in `tests/`.
4. Ensure deterministic passes precede probabilistic or fuzzy passes.
