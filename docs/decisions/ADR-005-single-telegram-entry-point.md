# ADR-005 — Single Telegram entry point for all update types

**Context.** Phase 3 needs to handle three kinds of incoming Telegram traffic on the same bot:
new customer messages (WF-1, already built in Phase 2), inline-keyboard callback queries
(Approve/Edit/Reject taps), and operator reply-to-message edit captures. Telegram's Bot API
allows exactly **one** registered webhook URL per bot token (`setWebhook`). n8n's Telegram Trigger
node registers its own webhook on activation. If WF-3 (the HITL workflow) had its own Telegram
Trigger node for callback queries, activating it would silently overwrite WF-1's existing webhook
registration — Telegram would start sending all updates to WF-3's URL instead, breaking customer
intake with no error surfaced anywhere in n8n or in this codebase.

**Decision.** WF-1's existing Telegram Trigger node is the single entry point for every Telegram
update type on this bot (`updates: ["message", "callback_query"]`). Immediately after the trigger,
a small IF-based router distinguishes: a `callback_query` (button tap) → routed to WF-3 via
Execute Workflow; a `message` arriving from the ops chat that is also a reply
(`reply_to_message` present) → treated as an operator's edit-capture, routed to WF-3; anything
else → the existing customer-intake pipeline, unchanged. WF-3 itself has **no trigger node of its
own** — it is invoked purely via Execute Workflow, receiving a `mode` field (`post_for_approval` /
`callback` / `edit_reply`) that determines which branch it runs.

**Consequences.**
- Rules out ever adding a second Telegram Trigger node anywhere on this n8n instance for this bot.
  Any future workflow needing Telegram updates must be wired through WF-1's router instead of
  registering its own trigger.
- WF-1 takes on a routing responsibility beyond pure intake, growing slightly more complex than a
  single-purpose workflow — accepted as the smaller cost versus a webhook registration race that
  would fail silently and be hard to diagnose (no error, just "customer messages stopped arriving"
  sometime after WF-3 was activated).
- The reply→ticket mapping for edit-capture uses a `TICKET-ID:<uuid>` footer embedded in the draft
  message text (parsed back out of `reply_to_message.text`), not n8n workflow static data — chosen
  because it needs no key-management across stateless webhook executions and is fully inspectable
  by a human just reading the Telegram thread. This is schema-free per the DB's frozen-schema
  constraint (no new column or table). Originally written as a bracketed `[ticket:<uuid>]` footer;
  changed to this bracket-free form in Phase 3 after discovering Telegram's default Markdown parse
  mode silently strips unmatched `[...]` as incomplete link syntax (wiki/gotchas.md #26).
