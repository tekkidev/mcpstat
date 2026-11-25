# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Report suspected vulnerabilities privately using
[GitHub's reporting form](https://github.com/tekkidev/mcpstat/security/advisories/new).
Include the mcpstat and Python versions, affected integration, reproduction steps
and potential impact. Suggested fixes are welcome. Do not include credentials or
production usage databases. Please do not report vulnerabilities through public issues.

You can expect:

- Acknowledgment within 48 hours
- Status update within 7 days
- Credit in the security advisory (if desired)

## Security Considerations

mcpstat stores data locally:

- **SQLite database**: Usage statistics stored in `./mcp_stat_data.sqlite` by default
- **Log files**: Optional audit logs stored in `./mcp_stat.log`

Ensure appropriate file permissions for sensitive deployments.

Logs omit arguments, results, and exception messages. Resource names can still contain
sensitive data. Restrict filesystem access and authorize analytics tools in the host
server. Local statistics and logs are mutable and do not provide tamper-proof evidence.
