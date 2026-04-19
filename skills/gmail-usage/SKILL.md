---
name: gmail-usage
description: Use this skill whenever the user wants to do anything with Gmail through the gmail-mcp tools. Triggers on mentions of email, inbox, Gmail, "send an email," "reply to," "archive," "check my email," "unread," "find the email from," "draft a message," "read that thread," or any request to search, read, draft, send, reply, archive, label, trash, or organize email messages. Also triggers on requests involving attachments (downloading files from email, attaching files to a reply). Covers multi-account workflows where the user has more than one Gmail address connected.
---

# Gmail Usage

Operational guide for the `gmail-mcp` tools. Follow these rules strictly when handling email on the user's behalf.

## Account selection

Always confirm which account to use when the user has more than one connected. Call `list_accounts` first if the user says something ambiguous like "check my email." Do not guess between a personal and a work address.

If the user explicitly names a context ("my work email," "the gmail I use for the consulting client"), map that to the matching account from `list_accounts`. If the mapping is not obvious, ask.

## Reading workflow

For single-message reads, call `read_email(account, message_id)`. Bodies are truncated at 20k chars by default. Only pass `full=True` when the user asks for the full content or when a truncated body is obviously cutting off something important (e.g., the key data is in the tail of the message).

For anything involving a reply or conversation context, call `get_thread(account, thread_id)` first. Never draft a reply from a single message in isolation when the thread has more than one message. Replying blind to the latest message misses context that changes the right response.

For attachments, the attachment metadata comes back inside `read_email` output. Call `save_attachment` only when the user actually wants the file locally. Do not download attachments speculatively.

## Sending workflow

Never call send directly. The tool chain is always:

1. `draft_email` or `draft_reply` to create a draft
2. Show the draft content to the user, summarize, and wait for explicit approval
3. `send_draft(account, draft_id)` once the user confirms

If the user says "send an email to X saying Y," interpret that as "draft an email to X saying Y and show me before sending." Confirm with the user before calling `send_draft`. This is a hard rule, not a preference.

When replying, always use `draft_reply` rather than `draft_email`. `draft_reply` preserves threading (`In-Reply-To`, `References`, `threadId`) so the message lands in the same conversation rather than starting a new thread.

Set `include_original=True` on `draft_reply` only when the user explicitly asks for a quoted original, or when the reply references something specific from the original that needs context.

## Search syntax

Use Gmail's native query operators, not natural language guesses:

- `is:unread`, `is:read`, `is:starred`
- `from:address@domain.com`, `to:address@domain.com`
- `subject:"exact phrase"`
- `has:attachment`, `filename:pdf`
- `newer_than:7d`, `older_than:1m`, `after:2024/01/01`, `before:2024/12/31`
- `label:name`, `-label:name` (negation)
- `in:inbox`, `in:sent`, `in:trash`

Combine with spaces for AND, `OR` for alternation, parentheses for grouping. Example: `from:alice@co.com (subject:invoice OR subject:receipt) newer_than:30d has:attachment`.

Default `max_results` is 10. Raise it only when the user asks for more or when the first page is clearly incomplete.

## Labels and organization

`get_labels(account)` returns ID + name. Label IDs like `INBOX`, `UNREAD`, `STARRED`, `SPAM`, `TRASH` are system labels; user labels have IDs like `Label_1234567890`.

`archive_email` removes the `INBOX` label so the message falls out of the inbox but stays searchable. Use this for "I'm done with this, get it out of my face."

`trash_email` moves to Trash. Use for things the user actively wants gone. Trash auto-purges after 30 days.

For custom labels by name, call `get_labels` first to find the ID, then `apply_label` or `remove_label`.

## Destructive actions

Confirm before any bulk destructive action (archiving more than 5 messages in one go, trashing anything, removing labels at scale). A short summary plus "proceed?" is enough; do not require formal approval for trivial single-message actions the user just requested.

Never call `remove_account` without the user explicitly asking to disconnect the account.

## Attachments

To attach files when drafting, pass absolute file paths as a comma-separated string to the `attachments` arg. Example: `attachments="/Users/me/Documents/proposal.pdf,/Users/me/images/logo.png"`.

To download an attachment from an incoming email, use `save_attachment`. Default save location is `~/Downloads/gmail-mcp/`. Let the user override with a `save_dir` if they want it elsewhere.

## Audit log

`view_audit_log` shows every mutation this server has performed. Offer this proactively if the user ever asks "what did you do with my email" or "did you send anything I didn't approve."

## Error handling

When a tool returns an error string, read it and explain in plain terms. Authentication errors ("Account X is not authenticated") mean call `add_account(X)`. Quota errors mean wait and retry. Identity mismatch errors during `add_account` mean the user signed in as the wrong Google account.

Do not retry blindly. Surface the error to the user with a clear next step.

## What not to do

- Do not send email without a draft step, ever.
- Do not guess the account when multiple are connected.
- Do not download attachments unless asked.
- Do not quote long original messages unless asked.
- Do not use `read_email` when `get_thread` is more appropriate.
- Do not call `remove_account` without explicit user instruction.
- Do not paste message bodies back to the user verbatim if they asked for a summary.
