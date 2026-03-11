# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Enhanced README.md with comprehensive documentation
- CONTRIBUTING.md with contribution guidelines
- LICENSE (MIT)
- ARCHITECTURE.md with detailed technical documentation
- TODO.md for tracking project improvements

### Changed
- Improved code documentation across all modules
- Enhanced CLI interface with better help text

## [0.1.0] - 2024-01-15

### Added
- Initial release of NullShift
- **DetectUntestedFunctions** step - Parses PR diffs to find untested Python functions
- **GenerateUnitTests** step - Uses Groq LLM to generate pytest unit tests
- **CreateTestPR** step - Creates GitHub PRs with generated tests
- CLI interface via Click
- Dry-run mode for local testing
- Support for custom LLM endpoints
- Comprehensive test suite with mocked external dependencies

### Features
- AST-based Python function detection
- Support for class methods and async functions
- Automatic test file path derivation
- Git branch creation and pushing
- GitHub PR creation with formatted description
- Support for multiple test directories

### Dependencies
- openai (OpenAI-compatible client)
- PyGithub (GitHub API)
- tree-sitter (AST parsing)
- click (CLI framework)
- pytest (testing)
- rich (terminal output)

---

## Upgrade Notes

### Upgrading to 0.1.0
This is the first stable release. No migration steps required.

---

## Deprecation Notices

None at this time.

---

## Known Issues

- Limited to Python function detection (classes, decorators support may be limited)
- Test generation quality depends on LLM capabilities
- Requires internet connection for LLM API calls

---

## Frequently Asked Questions

### Q: How does NullShift detect untested functions?
A: NullShift parses the git diff, extracts added/modified Python code, and uses AST analysis to find function definitions. It then checks if there are existing tests in the `tests/` or `test/` directories.

### Q: What LLM does NullShift use?
A: By default, NullShift uses Groq's Llama 3.3 70B model, but it supports any OpenAI-compatible endpoint.

### Q: Can I use NullShift without GitHub?
A: Yes! Use the `dry_run=True` option to generate tests locally without creating git branches or PRs.

### Q: Is NullShift safe to use?
A: NullShift is designed with safety in mind:
- Dry-run mode for testing
- Tests are created on a separate branch
- Human review is required before merging
- No automatic code execution

---

## Credits

- **Ravikiranreddybada** - Author and maintainer
- [Groq](https://groq.com/) - LLM API
- [Patchwork](https://github.com/patched-codes/patchwork) - Framework inspiration
- [PyGithub](https://github.com/PyGithub/PyGithub) - GitHub API client

---

## Migration Guides

### From 0.0.x to 0.1.0
This is the first major release. Please report any issues encountered during migration.

---

<!--
Markdown formatting notes:
- Use links like `[0.1.0]: https://github.com/NullShift/NullShift/releases/tag/v0.1.0`
- Keep sections in reverse chronological order
- Include relevant links to issues/PRs when available
-->

