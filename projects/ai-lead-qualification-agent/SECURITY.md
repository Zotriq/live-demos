# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public issue
2. Email the details to the maintainer
3. Include steps to reproduce if possible
4. Allow reasonable time for a fix before disclosure

## Security Best Practices for Deployment

- Never commit API keys or secrets to the repository
- Always use environment variables for sensitive configuration
- Enable webhook secret validation in production
- Use HTTPS in production
- Keep dependencies updated
- Review AI-generated email content before sending (human approval is enforced by default)
- Restrict CORS origins to your actual domains
- Use strong database passwords
- Enable PostgreSQL SSL in production
