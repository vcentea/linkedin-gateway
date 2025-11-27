# Privacy Policy

**LinkedIn Gateway Chrome Extension**

*Last Updated: November 26, 2025*

---

## 1. Introduction

This Privacy Policy describes how LinkedIn Gateway ("we", "our", or "the Extension") collects, uses, and protects your information when you use our Chrome extension and related services.

LinkedIn Gateway is a productivity tool that helps you interact with LinkedIn and AI services through a secure proxy. We are committed to protecting your privacy and being transparent about our data practices.

---

## 2. Information We Collect

### 2.1 LinkedIn Integration

When you connect your LinkedIn account, we collect:

- **LinkedIn Session Cookies**: Temporary authentication cookies that allow the Extension to make requests on your behalf. These include cookies such as `li_at`, `JSESSIONID`, and `csrf-token`.
- **LinkedIn Profile Information**: Your public profile data (name, profile picture, headline) for display purposes within the Extension.
- **CSRF Tokens**: Security tokens required to make authenticated requests to LinkedIn.

**We do NOT collect or store:**
- Your LinkedIn password
- Private messages content (unless explicitly requested for a specific feature)
- Your LinkedIn connections' private information

### 2.2 Gemini AI Integration

When you connect your Google account for Gemini AI features, we collect:

- **OAuth Access Tokens**: Temporary tokens that allow the Extension to access Google's AI services on your behalf.
- **Google Email Address**: For identification and display purposes within the Extension.
- **Profile Picture URL**: For display purposes in the Extension dashboard.

**We do NOT collect or store:**
- Your Google password
- Your Gmail content
- Your Google Drive files
- Any Google Workspace data

### 2.3 API Keys

- **Generated API Keys**: We generate and store API keys that authenticate your requests to our backend services.
- **Instance Identifiers**: Unique identifiers for each browser instance where the Extension is installed.

### 2.4 Usage Data

- **Request Logs**: We log API requests for security, debugging, and rate limiting purposes. These logs include timestamps, endpoints accessed, and response status codes.
- **Error Logs**: Technical error information to help us improve the service.

**We do NOT collect:**
- Browsing history
- Form data from other websites
- Personal files from your computer
- Location data

---

## 3. How We Use Your Information

We use the collected information to:

1. **Provide Core Services**: Enable LinkedIn API functionality and Gemini AI features through our secure proxy.
2. **Authentication**: Verify your identity and maintain secure sessions.
3. **Rate Limiting**: Enforce fair usage limits to ensure service quality for all users.
4. **Security**: Detect and prevent unauthorized access, abuse, or fraud.
5. **Debugging**: Identify and fix technical issues.
6. **Service Improvement**: Analyze usage patterns to improve the Extension (aggregated, non-personal data only).

---

## 4. Data Storage and Security

### 4.1 Where Data is Stored

- **Local Storage**: Session cookies, tokens, and preferences are stored locally in your browser using Chrome's secure storage APIs.
- **Backend Servers**: API keys and minimal session metadata are stored on our secured servers.
- **Database**: We use PostgreSQL with encrypted connections for data storage.

### 4.2 Security Measures

- **Encryption in Transit**: All data transmitted between the Extension and our servers uses TLS 1.3 encryption.
- **Encrypted Storage**: Sensitive credentials are encrypted at rest.
- **API Key Hashing**: API keys are stored as one-way hashes; we cannot retrieve your original key.
- **No Password Storage**: We never store or have access to your LinkedIn or Google passwords.
- **Session Timeouts**: OAuth tokens and sessions expire and require re-authentication.

### 4.3 Data Retention

- **Session Data**: Cleared when you disconnect your account or uninstall the Extension.
- **API Logs**: Retained for 30 days for security and debugging purposes, then automatically deleted.
- **Account Data**: Retained while your account is active; deleted upon account deletion request.

---

## 5. Third-Party Services

### 5.1 LinkedIn

The Extension interacts with LinkedIn's services. Your use of LinkedIn through our Extension is also subject to:
- [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement)
- [LinkedIn Privacy Policy](https://www.linkedin.com/legal/privacy-policy)

### 5.2 Google (Gemini AI)

The Extension uses Google's OAuth 2.0 for authentication and Google's AI services. Your use is subject to:
- [Google Terms of Service](https://policies.google.com/terms)
- [Google Privacy Policy](https://policies.google.com/privacy)
- [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy)

### 5.3 Hosting Providers

Our backend services are hosted on secure cloud infrastructure. These providers have their own privacy policies and security certifications.

---

## 6. Data Sharing

**We do NOT sell your data.**

We may share data only in these limited circumstances:

1. **With Your Consent**: When you explicitly authorize sharing.
2. **Service Providers**: With trusted service providers who help operate our services (cloud hosting, error tracking), under strict confidentiality agreements.
3. **Legal Requirements**: If required by law, court order, or government request.
4. **Safety**: To protect the safety, rights, or property of users or the public.

---

## 7. Your Rights and Choices

### 7.1 Access and Control

You have the right to:

- **View**: See what data we store about you by contacting us.
- **Disconnect**: Remove LinkedIn or Gemini connections at any time via the Extension dashboard.
- **Delete**: Request deletion of your account and associated data.
- **Export**: Request a copy of your data in a portable format.

### 7.2 How to Exercise Your Rights

- **Disconnect Accounts**: Use the "Disconnect" button in the Extension dashboard.
- **Delete API Key**: Use the Extension settings to delete your API key.
- **Account Deletion**: Contact us at privacy@ainnovate.tech to request full account deletion.
- **Data Export**: Contact us at privacy@ainnovate.tech.

### 7.3 Cookie Preferences

The Extension requires certain cookies to function. You can disable the Extension entirely if you do not wish to allow cookie collection.

---

## 8. Children's Privacy

LinkedIn Gateway is not intended for use by individuals under 16 years of age. We do not knowingly collect personal information from children. If we become aware that a child has provided us with personal information, we will take steps to delete such information.

---

## 9. International Users

Our servers are located in [Europe/USA]. By using the Extension, you consent to the transfer of your information to our servers. We comply with applicable data protection laws, including GDPR for European users.

### GDPR Rights (EU Users)

If you are in the European Union, you have additional rights:
- Right to access
- Right to rectification
- Right to erasure ("right to be forgotten")
- Right to restrict processing
- Right to data portability
- Right to object
- Rights related to automated decision-making

To exercise these rights, contact us at privacy@ainnovate.tech.

---

## 10. Changes to This Policy

We may update this Privacy Policy from time to time. We will notify you of significant changes by:
- Updating the "Last Updated" date at the top of this policy
- Displaying a notice in the Extension
- Sending an email notification (if you've provided an email address)

Your continued use of the Extension after changes constitutes acceptance of the updated policy.

---

## 11. Open Source

LinkedIn Gateway Core is open source. You can review our code on GitHub to verify our privacy practices:
- [GitHub Repository](https://github.com/vcentea/LinkedinGateway)

---

## 12. Contact Us

If you have questions, concerns, or requests regarding this Privacy Policy, please contact us:

- **Email**: privacy@ainnovate.tech
- **Website**: https://ainnovate.tech
- **GitHub Issues**: https://github.com/vcentea/LinkedinGateway/issues

---

## 13. Summary

| Data Type | Collected | Stored Locally | Stored on Server | Shared with Third Parties |
|-----------|-----------|----------------|------------------|---------------------------|
| LinkedIn Cookies | ✅ | ✅ | ✅ (encrypted) | ❌ |
| LinkedIn Profile | ✅ | ✅ | Minimal | ❌ |
| Google OAuth Tokens | ✅ | ✅ | ✅ (encrypted) | ❌ |
| Google Email | ✅ | ✅ | ❌ | ❌ |
| API Keys | ✅ | ✅ | ✅ (hashed) | ❌ |
| Request Logs | ✅ | ❌ | ✅ (30 days) | ❌ |
| Passwords | ❌ | ❌ | ❌ | ❌ |
| Browsing History | ❌ | ❌ | ❌ | ❌ |

---

*This Privacy Policy is effective as of November 26, 2025.*

