# n8n-workflow-export — delta

## MODIFIED Requirements

### Requirement: Export SHALL fetch all 7 OpsPilot workflows

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
