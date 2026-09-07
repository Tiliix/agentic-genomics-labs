# Public newsletter repository

- This repository is PUBLIC: `Tiliix/agentic-genomics-labs`.
- "Publish a lab", "newsletter", "LinkedIn", and "share the tutorial" mean this
  repository, not the private product repository.
- Copilomics prototype work belongs in the independent PRIVATE repository
  `Tiliix/copilomics`. Do not implement, commit, or track product work here.
- The configured local newsletter checkout is `C:\workspaces\agentic-genomics-labs`;
  the private product checkout is `C:\workspaces\copilomics`.
- Before any publication, verify the working directory and `git remote -v`.
  Never add a private product remote or merge/cherry-pick a whole product branch.
- Publish only explicitly selected educational files after reviewing their
  content, fixtures, outputs, licenses, and outgoing history. Public examples
  must work without private repository access.
- Preserve published lab paths and newsletter URLs. Keep unpublished product
  workflows and internal evaluations private even if they resemble a lab.
- Run the existing affected lab checks and `python scripts/check_public_boundary.py --all`.
  Enable the committed push guard with `git config core.hooksPath .githooks`.
- Use public issues for reader-facing lab work only. A private Project does not
  make public repository issues confidential.
