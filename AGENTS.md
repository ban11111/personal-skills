# Personal Skills authoring contract

- Each `skills/<id>` is independently installable; use relative links inside it.
- Keep SKILL.md focused. Route detailed procedures to references, with a reason to read each.
- Preserve user intent. Case-specific art, timing, motion, device, and deployment choices are not universal rules.
- Do not vendor private project source, original character art, credentials, local paths, third-party skills or runtimes.
- Distinguish measured observations from hypotheses and untested suggestions. Synthetic fixtures prove checker behavior only.
- Run `python scripts/validate_repo.py` and `python -m unittest discover -s tests -v` before publishing.
- Execute modified helper scripts on meaningful valid and invalid inputs. Do not claim automated tests establish visual anatomy or physical-device performance.
- Add catalog entries and UI metadata for new skills. Preserve unrelated skills and installed destinations.
