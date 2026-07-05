# General FAQ

## What is Acme Cloud Suite?

Acme Cloud Suite is a team project and task-management SaaS built by Acme Inc. It helps teams
plan work, track tasks through boards and lists, collaborate on projects, and connect their other
tools through a REST API. Acme Cloud Suite runs in the browser and also ships a desktop app that
keeps a local cache in sync with your account in the cloud.

## Who is Acme Cloud Suite for?

Acme Cloud Suite is designed for teams of all sizes:

- **Small teams and freelancers** who need a lightweight way to track tasks can start on the
  Free plan.
- **Growing teams** that need more users and storage typically move to Starter or Pro.
- **Larger organizations** with compliance, single sign-on, and support needs typically choose
  Enterprise.

## What plans are available?

Acme Cloud Suite offers four plans, billed monthly per user:

| Plan | Price | Users | Storage |
|---|---|---|---|
| Free | $0 | Up to 3 users | 1GB |
| Starter | $9/user/month | Up to 20 users | 20GB |
| Pro | $19/user/month | Unlimited users | 200GB |
| Enterprise | Custom pricing via sales | Unlimited users | Unlimited storage |

Starter and Pro also support annual billing: pay for 10 months and get 12 months of service
(about a 17% discount versus paying monthly). See the Billing & Plans document for full details
on upgrading, downgrading, and annual billing.

## Does Acme Cloud Suite have an API?

Yes. Acme Cloud Suite exposes a REST API at `https://api.acmecloudsuite.example.com/v1` for
integrations, automations, and custom tooling. Authentication uses an API key sent in the
`Authorization: Bearer <key>` header. Rate limits depend on your plan — see the API Guide
document for details on authentication and rate limits.

## What kind of support do I get?

Support response times depend on your plan:

- **Free and Starter**: 48-hour email response.
- **Pro**: 24-hour priority support.
- **Enterprise**: 4-hour response, with a dedicated account manager and phone support.

## Is my data secure?

Two-factor authentication (2FA), based on TOTP (time-based one-time codes), is available on
every plan, including Free. Single sign-on (SSO) via SAML is available on the Enterprise plan.

## What happens if I cancel my account?

If you cancel, your account data is retained for 90 days in case you want to reactivate. After
90 days, the data is permanently deleted. See the Refund & Cancellation Policy document for full
details, including how refunds and prorations work.

## Where do I go for troubleshooting help?

If you're having trouble logging in (including 2FA codes not matching), see
"Troubleshooting: Login & 2FA." If the desktop app is stuck syncing or feels slow, see
"Troubleshooting: Sync & Performance."
