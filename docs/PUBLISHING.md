# Publishing QuotaCompass

QuotaCompass publishes Python distributions from GitHub Actions with PyPI Trusted Publishing. No long-lived PyPI API token belongs in GitHub, a local config file, or an agent prompt.

## One-time account setup

1. Enable two-factor authentication on the PyPI account and save the recovery codes somewhere separate from the authenticator.
2. Create the `pypi` and `testpypi` environments in the GitHub repository settings. Require a reviewer for `pypi`; optionally restrict it to tags matching `v*`.
3. On PyPI, add a pending GitHub Actions publisher with these exact values:
   - PyPI project name: `quotacompass`
   - GitHub owner: `AIAtHome-Adam`
   - Repository: `QuotaCompass`
   - Workflow: `publish.yml`
   - Environment: `pypi`
4. TestPyPI is a separate service and account. After creating and verifying that account, add the same pending publisher there with environment `testpypi`.

A pending publisher does not reserve the package name. Complete the first publish promptly after registering it.

## Release procedure

1. Choose a version that has never been uploaded to the target index. PyPI does not permit reusing an uploaded filename or release version, even after deletion.
2. Update `pyproject.toml`, `CHANGELOG.md`, and the README release status.
3. Run the full local verification commands from `IMPLEMENTATION_NOTES.md` and inspect `git status` plus the staged diff.
4. Push the release commit and wait for every CI matrix job to pass.
5. Manually run **Publish Python package** from the GitHub Actions page. This builds once, audits the distributions, and publishes that exact artifact to TestPyPI.
6. Test installation in a clean environment. TestPyPI may not contain dependencies, so install dependencies from normal PyPI or use `--no-deps` for the package-only smoke test.
7. Create a non-prerelease GitHub release whose tag is exactly `v<project version>`. The workflow rejects a mismatched tag, rebuilds and audits once, waits at the protected `pypi` environment, and publishes the same artifact after approval.
8. Verify the public PyPI page, hashes, metadata, and a clean `python -m pip install quotacompass` before announcing the release.

The TestPyPI manual dispatch never publishes to production. Production publication occurs only for a non-prerelease GitHub release and is additionally gated by the `pypi` environment.
