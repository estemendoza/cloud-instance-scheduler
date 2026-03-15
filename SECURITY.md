# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Cloud Instance Scheduler, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email security concerns to the project maintainers. Include:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and aim to provide a fix or mitigation within 7 days for critical issues.

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |

## Security Features

CIS implements comprehensive security controls appropriate for managing cloud provider credentials:

- **Credential encryption**: All cloud provider credentials encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256)
- **Dual authentication**: JWT tokens for browser sessions, bcrypt-hashed API keys for programmatic access
- **Role-based access control**: Three roles (admin, operator, viewer) with least-privilege defaults
- **Rate limiting**: Endpoint-specific limits on authentication and sensitive operations
- **Audit logging**: All security-relevant events tracked with IP address and user agent
- **Security headers**: HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **Request size limits**: 10 MB maximum to prevent abuse
- **API key expiration**: 90-day default with expiry warnings
- **Generic error messages**: 403 responses don't leak role or permission information

## Best Practices for Deployment

- Use strong, unique values for `ENCRYPTION_KEY` and `JWT_SECRET_KEY`
- Run behind a reverse proxy (nginx) with TLS termination
- Set `DISABLE_DOCS=True` in production to hide OpenAPI documentation
- Rotate API keys regularly (90-day default enforced)
- Review audit logs periodically for suspicious activity
- Use a secrets manager (AWS Secrets Manager, HashiCorp Vault) for production encryption keys
