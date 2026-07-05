# API Guide: Authentication & Rate Limits

Acme Cloud Suite provides a REST API for building integrations, automations, and custom
tooling on top of your workspace data.

## Base URL

All API requests are made against:

```
https://api.acmecloudsuite.example.com/v1
```

## Authentication

Acme Cloud Suite's API uses API-key authentication. Generate an API key from
**Settings > Developer > API Keys**, then include it in the `Authorization` header of every
request as a bearer token:

```
Authorization: Bearer <key>
```

Requests without a valid `Authorization` header, or with an expired or revoked key, are
rejected.

### Example request

```bash
curl -X GET "https://api.acmecloudsuite.example.com/v1/tasks" \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json"
```

A successful response returns a JSON body with a `200 OK` status.

## Rate limits

API rate limits depend on your Acme Cloud Suite plan:

| Plan | Rate limit |
|---|---|
| Starter | 100 requests/minute |
| Pro | 600 requests/minute |
| Enterprise | Custom (set per contract with your account manager) |

Rate limits are applied per API key, based on the plan your workspace is on. If your
integration needs a higher limit than your plan provides, Enterprise customers can arrange a
custom rate limit with their account manager.

## Common error codes

| Status | Meaning | Typical cause |
|---|---|---|
| `401 Unauthorized` | The request is missing a valid API key, or the key is invalid/expired/revoked. | Missing `Authorization` header, malformed bearer token, or a key that was rotated/revoked in Settings. |
| `429 Too Many Requests` | You've exceeded your plan's rate limit. | Sending more requests per minute than your plan allows (100/min on Starter, 600/min on Pro). Back off and retry after the time indicated in the `Retry-After` response header. |

Other standard HTTP status codes (`400` for malformed requests, `403` for permission issues,
`404` for missing resources, `500` for server errors) may also be returned; consult the
response body for a `message` field with more detail.

## Best practices

- Store API keys securely and never commit them to source control.
- Rotate API keys periodically from **Settings > Developer > API Keys**.
- Implement retry logic with backoff for `429` responses, respecting the `Retry-After` header.
- Use a dedicated API key per integration so you can revoke access to one integration without
  affecting others.

For questions about API access on your plan, or to request a custom rate limit on Enterprise,
contact support according to your plan's SLA: 48 hours for Free/Starter, 24 hours for Pro, or
4 hours for Enterprise.
