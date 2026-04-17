# 10x National Address Database Submission Tool (NAD-ST)

## Local Development

To run the app locally, you will need to have Python version 3.11.7 and Node.js
version 18.17.1 installed.

Install [poetry](https://python-poetry.org/docs/#installation) so that you can
run tests and scripts locally.

Clone the repostiory:

```bash
git clone https://github.com/GSA-TTS/10x-nad-st/
```

In order to set up a local development environment, you will need to download
[Docker](https://www.docker.com/).

To set the necessary environment variables, copy the `sample.env` file to a new
file named `.env` in the same directory:

```bash
cp sample.env .env
```

Update all settings defaulted to `<add_a_key_here>`.

### login.gov Setup

This application uses **OpenID Connect Private Key JWT** for authentication with login.gov.

#### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `LOGINGOV_CLIENT_ID` | Your app's issuer/client ID registered with login.gov |
| `LOGINGOV_PRIVATE_KEY` | RSA private key in PEM format |

#### Generating a Private Key

Generate an RSA private key in traditional format (required for login.gov):

```bash
openssl genrsa 2048 | openssl rsa -traditional > private.pem
```

This generates a key in the format `-----BEGIN RSA PRIVATE KEY-----` (not `-----BEGIN PRIVATE KEY-----`).

#### Converting for .env File

The `.env` file expects the key with `\n` as literal two-character escape sequences. Use this Python script to convert:

```python
# Convert PEM key to .env format
with open('private.pem', 'r') as f:
    key = f.read()

# Replace actual newlines with \n escape sequence
env_key = key.strip().replace('\n', '\\n')

# Update .env file
import os
from dotenv import load_dotenv
load_dotenv()

# Read existing .env
with open('.env', 'r') as f:
    lines = f.readlines()

# Replace LOGINGOV_PRIVATE_KEY line
new_lines = []
for line in lines:
    if line.startswith('LOGINGOV_PRIVATE_KEY='):
        new_lines.append(f'LOGINGOV_PRIVATE_KEY={env_key}\n')
    else:
        new_lines.append(line)

with open('.env', 'w') as f:
    f.writelines(new_lines)
```

Or manually: ensure your key starts with `-----BEGIN RSA PRIVATE KEY-----\n` (NOT `-----BEGIN PRIVATE KEY-----`).

**Important:** The key format must be:
- Header: `-----BEGIN RSA PRIVATE KEY-----` (RSA, not just PRIVATE KEY)
- Each line joined with `\n` (backslash + n, not actual newlines)

#### Registering with login.gov

1. In the login.gov developer dashboard, create a new application
2. Select **OpenID Connect Private Key JWT** as the authentication protocol
3. Generate a key pair (see above) and upload the **public key** or certificate
4. Set the **Issuer** (must match exactly in your app):
   ```
   urn:gov:gsa:openidconnect.profiles:sp:sso:agency_name:app_name
   ```
   Example: `urn:gov:gsa:openidconnect.profiles:sp:sso:gsa:10x-nad-st`
5. Configure **Redirect URIs** for your environment:
   - Local development (Docker): `http://127.0.0.1:8080/auth/callback/logingov`
   - Or: `http://localhost:8080/auth/callback/logingov`
   - Note: The callback path is `/auth/callback/<provider>` (includes `/auth` prefix from blueprint)
6. Optionally configure **Push Notification URL** (not required - leave blank)

#### Service Level (IAL)

The application uses **Authentication Only** (`urn:acr.login.gov:auth-only`) by default. This is IAL1 - requires email, password, and MFA, but no identity verification.

| Service Level | ACR Value | User Verification | Use Case |
|--------------|---------|-----------------|---------|
| Authentication Only | `urn:acr.login.gov:auth-only` | None (IAL1) | Public-facing apps where identity proofing isn't needed |
| Identity Verification | `urn:acr.login.gov:verified` | Basic ID proofing | When you need to verify user identity，但不要求IAL2 |
| Identity Verification + Facial Match | `urn:acr.login.gov:verified-facial-match-required` | IAL2 compliant | Regulated systems requiring full identity proofing |

To change the service level, update `acr_values` in `nad_ch/config/base.py`.

#### Authentication Assurance Level (AAL)

login.gov requires MFA by default (AAL2 minimum). The application currently relies on login.gov's default AAL2 (MFA required, remember device up to 30 days).

| AAL Level | ACR Value | MFA Requirements | Remember Device |
|-----------|-----------|-----------------|-----------------|
| AAL2 (Default) | `urn:gov:gsa:ac:classes:sp:PasswordProtectedTransport:duo` | MFA required | Allowed up to 30 days |
| AAL2 (Strict) | `http://idmanagement.gov/ns/assurance/aal/2` | MFA required | Disallowed |
| AAL2 (Phishing-resistant) | `http://idmanagement.gov/ns/assurance/aal/2?phishing_resistant=true` | WebAuthn, PIV/CAC, or Face/Touch Unlock | Disallowed |
| AAL3 | `http://idmanagement.gov/ns/assurance/aal/3?phishing_resistant=true` | Phishing-resistant MFA + verifier impersonation resistance | Disallowed |

Note: login.gov does not allow strict AAL1 (password-only, no MFA).

To configure AAL, update the `acr_values` in `nad_ch/controllers/web/routes/auth.py` to include both IAL and AAL (space-separated), e.g.:
```
acr_values="urn:acr.login.gov:auth-only http://idmanagement.gov/ns/assurance/aal/2?phishing_resistant=true"
```

#### Attribute Bundle (Scopes)

The application requests the following scopes by default: `openid`, `email`, `profile`.

| Scope | Attribute | Description |
|-------|-----------|-------------|
| `openid` | (required) | Required for OIDC - enables authentication |
| `email` | `email` | User's primary email address |
| `all_emails` | `email` (array) | All email addresses on the account |
| `profile` | `given_name`, `family_name` | User's name |
| `profile:name` | `given_name`, `family_name` | User's name |
| `profile:birthdate` | `birthdate` | User's birthdate (requires IAL2) |
| `profile:verified_at` | `verified_at` | Timestamp when identity was verified |
| `address` | `address` | User's address (requires IAL2) |
| `phone` | `phone` | User's phone number (requires IAL2) |
| `social_security_number` | `social_security_number` | SSN (requires IAL2) |
| `x509_subject` | `x509_subject` | PIV/CAC certificate subject |
| `x509_presented` | `x509_presented` | Whether PIV/CAC was presented |

To change scopes, update `scopes` in `nad_ch/config/base.py`:

```python
"scopes": ["openid", "email", "all_emails", "profile:verified_at"],
```

Install frontend dependencies and run in development mode:

```bash
cd nad_ch/controllers/web
npm install
npm run dev
```

Return to the project's root directory and run the following command to build
the app and start up its services:

```bash
docker compose up --build
```

To create database migrations (add comment associated with migration in quotes):

```bash
docker exec nad-ch-dev-local poetry run alembic revision --autogenerate -m "ENTER COMMENT"
```

To run database migrations:

```bash
docker exec nad-ch-dev-local poetry run alembic upgrade head
```

To downgrade database migrations:

```bash
docker exec nad-ch-dev-local poetry run alembic downgrade <enter down_revision id>
```

## Testing

Some tests in the test suite are dependent on Minio operations and access key is required. To Create a Minio access key, visit the Minio webui at [minio-webui](localhost:9001) and under User/Access Keys, click Create access key. Save the credentials to your .env file under S3_ACCESS_KEY and S3_SECRET_ACCESS_KEY.

Run the test suite as follows:

```bash
poetry run test
```
