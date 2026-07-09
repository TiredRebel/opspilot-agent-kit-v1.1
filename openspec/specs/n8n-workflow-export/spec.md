# n8n-workflow-export

## Purpose

Defines the behavior of the script that exports OpsPilot's live n8n workflows into the repo
(`workflows-n8n/`), so the committed workflow definitions can be refreshed from the running n8n
instance without leaking secrets or pulling in unrelated workflows.

## Requirements

### Requirement: Export SHALL fetch only OpsPilot's own workflows
The export script SHALL fetch exactly the 7 workflows belonging to OpsPilot (matched by name:
`WF-1 Intake & Triage`, `WF-2 Draft Answer`, `WF-3 Human-in-the-loop`, `WF-4 SLA Watchdog`,
`WF-5 Daily Digest`, `WF-6 Outbound Delivery`, `WF-7 Event Publisher`) from the live n8n instance,
and SHALL NOT include any other workflow present on that instance.

#### Scenario: The shared n8n instance has unrelated workflows
- **WHEN** the export script runs against an n8n instance that also hosts workflows unrelated to
  OpsPilot
- **THEN** only the 7 named OpsPilot workflows SHALL be written to `workflows-n8n/`, and no
  unrelated workflow SHALL appear in the output

#### Scenario: Export includes a RabbitMQ credential reference
- **WHEN** a node has a `credentials.rabbitmq` reference from the live instance
- **THEN** the exported file SHALL have `null` at `credentials.rabbitmq.id`, with
  `credentials.rabbitmq.name` preserved as `"RabbitMQ - OpsPilot"`

### Requirement: Exported workflows SHALL be directly re-importable
Each exported file SHALL contain only the fields n8n needs to import a workflow (`name`, `nodes`,
`connections`, `settings`), matching the shape already used by `n8n/workflows/*.json`.

#### Scenario: An export is fetched from the live API
- **WHEN** a workflow is fetched via `GET /workflows/{id}`
- **THEN** the written file SHALL contain only `name`, `nodes`, `connections`, and `settings` —
  instance metadata (`id`, `active`, `createdAt`, `updatedAt`, `versionId`, `tags`, `staticData`,
  `pinData`, `meta`) SHALL be stripped

### Requirement: Known secret-bearing values SHALL be redacted before writing
Any value at a path where the corresponding committed `n8n/workflows/*.json` file has a `PLACEHOLDER_*`/`*_PLACEHOLDER` token SHALL be overwritten back to that same placeholder token in the exported file. Credential `.id` fields SHALL always be nulled.

#### Scenario: Export includes a live-patched ops chat ID
- **WHEN** a node's `chatId` parameter (or equivalent condition value) holds the real ops chat ID
  live, and the corresponding committed file has `PLACEHOLDER_OPS_CHAT_ID` at that same path
- **THEN** the exported file SHALL contain `PLACEHOLDER_OPS_CHAT_ID` at that path, not the real
  chat ID

#### Scenario: Export includes a credential reference
- **WHEN** a node has a `credentials.<key>.id` value from the live instance
- **THEN** the exported file SHALL have `null` at that path, with `credentials.<key>.name`
  preserved

### Requirement: The export SHALL report drift beyond known redaction points
After redacting, the script SHALL diff each exported file against its `n8n/workflows/` counterpart
and print any remaining differences, without failing the export.

#### Scenario: Live workflow has diverged from the committed version
- **WHEN** a live workflow contains a change (e.g. a node parameter edited directly in the n8n UI)
  that isn't accounted for by the known placeholder/credential redaction rules
- **THEN** the script SHALL print that difference as part of its output, so it's visible for human
  review, rather than silently discarding or silently committing it
