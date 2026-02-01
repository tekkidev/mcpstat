# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in mcpstat, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer at hello@vadim.dev with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

You can expect:

- Acknowledgment within 48 hours
- Status update within 7 days
- Credit in the security advisory (if desired)

## Security Considerations

mcpstat stores data locally:

- **SQLite database**: Usage statistics stored in `./mcp_stat_data.sqlite` by default
- **Log files**: Optional audit logs stored in `./mcp_stat.log`

Ensure appropriate file permissions for sensitive deployments.
