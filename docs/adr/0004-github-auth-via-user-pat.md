# GitHub auth via user-provided PAT; OAuth App deferred

Status: accepted

To auto-create a Target Repo on the user's GitHub account, Lingua must act as the user — the former global server PAT cannot create repos in someone else's account. For v1 we take a **user-provided Personal Access Token**, stored in the Credential Vault and used both to create the repo (`POST /user/repos`) and to push on Publish. A GitHub App + OAuth flow is deferred.

## Considered options

- **GitHub App + OAuth** — best UX (one "Connect GitHub" button, no copy-paste) and best security (narrow, revocable, short-lived tokens). Rejected for v1: it needs a registered App with a callback URL, which is painful for self-hosters on localhost/LAN, and a central App would mean the project operates shared infra — at odds with "clone and self-host". Revisit if a hosted multi-user Lingua appears.
- **Keep one global server PAT** — cannot create repos on the user's behalf; defeats the feature.

## Consequences

- The Settings page has a GitHub PAT field; the user manages scope and expiry. Recommend a fine-grained PAT with repo create + contents.
- The token-injection plumbing already in place (`workspace._with_token`, the publish `credential.helper`) is reused, now sourcing the PAT from the vault instead of env.
- The vault and Settings UI are designed so an OAuth access token can later slot into the same storage without a schema change.
