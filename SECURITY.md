# Security Notes

## Known Scanner Findings

### DOMPurify innerHTML Usage (False Positive)

**File:** `frontend/vendor/dompurify.min.js`
**Finding:** Static analysis tools may flag `innerHTML` usage on line 2
**Status:** False positive - no action required

**Explanation:** DOMPurify is a security library specifically designed to sanitize HTML and prevent XSS attacks. The `innerHTML` usage flagged by scanners is internal to the library's sanitization logic, not a vulnerability.

**References:**
- [DOMPurify GitHub](https://github.com/cure53/DOMPurify)
- [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)

## Security Controls

| Control | Implementation |
|---------|----------------|
| XSS Prevention | All user content sanitized via DOMPurify before rendering |
| Authentication | Cognito JWT validation by AgentCore Runtime |
| Memory Isolation | Per-user namespaces using JWT `sub` claim |
| URL Allowlisting | Tools only fetch from whitelisted AWS domains |
| SNS Scoping | Agent can only publish to pre-configured topic |
| Secrets Management | Credentials loaded from AWS Secrets Manager at runtime |
