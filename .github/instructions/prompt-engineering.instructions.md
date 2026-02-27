---
applyTo: '*'
description: 'Guidance for creating, testing, and maintaining prompts and AI assistant templates.'
---

# Prompt Engineering Instructions

- Keep prompts explicit: include role, goal, input format, output format, and constraints.
- Provide few-shot examples when applicable; keep examples minimal but representative.
- Define expected output schema (JSON, markdown table, file path) and provide a strict post-processing step.
- Include tests for prompts: small input cases with expected outputs to detect regressions.
- Version prompts in the repository and refer to them from code (do not hardcode in app source).
- When prompts interact with user data, validate and sanitize inputs and follow principle of least privilege for any downstream actions.
- Document any model-specific assumptions (token limits, recommended temperature, model family).
