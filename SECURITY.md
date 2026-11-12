# Security

The optional helper processes untrusted JSON with Python's JSON parser. It does not execute input as code, fetch URLs, access credentials, or change account settings. Input size is limited to 1 MiB. Duplicate JSON fields, nonfinite values, invalid budget fractions, and ambiguous quota selection are handled explicitly.

These instructions do not replace the AI host's permissions, approvals, or hard usage limits. Review generated changes and use the host's normal sandbox controls.

## Report a vulnerability

Please do not put credentials, private transcripts, real quota data, or exploit details in a public issue. Use GitHub's private reporting option if it is available on the repository's Security tab. Otherwise, open an issue titled **Private security report requested** with no sensitive details so a maintainer can arrange a private channel.

Report ordinary bugs through [GitHub Issues](https://github.com/iliass-coder/Low-credit-mode/issues). Include the project version and a minimal synthetic example.
