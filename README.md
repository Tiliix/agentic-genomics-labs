# Agentic Genomics Labs

Public, self-contained educational labs accompanying the LinkedIn newsletter.
Readers do not need access to any private repository.

## Published labs

| Challenge | Lab |
| --- | --- |
| 01 | [Pipeline automation](labs/scenario-01-pipeline-automation/README.md) |
| 02 | [Variant interpretation](labs/scenario-02-variant-interpretation/README.md) |
| 03 | [Single-cell analysis](labs/scenario-03-single-cell/README.md) |

Start with the [lab catalog](labs/README.md), then follow the selected lab's setup
guide. Use public or synthetic data and your own cloud resources. These examples
are for education and research, not clinical or wet-lab decisions.

## What belongs here

- Published tutorials, standalone example code, and approved public/synthetic fixtures.
- Reader questions, lab bugs, and educational improvements.
- Reviewed lab releases accompanying newsletter editions.

Product application code, internal evaluations, deployment details, and product
planning do not belong in this public repository. A private branch or folder
inside a public repository does not provide confidentiality.

## Publishing a newsletter lab

1. Work in a separate clone of this public repository.
2. Select only the educational example intended for publication. Never merge
   a private product branch or mirror a private repository here.
3. Review source, fixtures, outputs, and commit history for private information,
   credentials, and redistribution rights. Keep existing lab URLs stable.
4. Run the lab's existing checks and the repository boundary check:
   `python scripts/check_public_boundary.py --all`.
5. Open a public pull request, review the diff, and publish a tag/release for the
   newsletter edition after merging.

Install the pinned gitleaks version described in [SECURITY.md](SECURITY.md), then
enable the local commit and push guards once per clone:

```console
git config core.hooksPath .githooks
```

The guard rejects prototype paths in outgoing history and pushes to an unexpected
repository. It is a defense against mistakes, not a substitute for content review.
See [SECURITY.md](SECURITY.md) for credential handling and secret-scanning setup.

## License

Original lab code is available under the [MIT License](LICENSE). Third-party code,
datasets, and services remain subject to their respective licenses and terms;
the repository license does not grant rights to those materials.
