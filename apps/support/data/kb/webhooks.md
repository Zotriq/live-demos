# Webhooks

- Add webhooks in Settings → Integrations → Webhooks. Events: report.ready, import.finished, alert.triggered.
- Your endpoint must answer with a 2xx status within 10 seconds, or the delivery counts as failed.
- Failed deliveries are retried 5 times over 24 hours. After that the webhook is paused and admins get an email.
- Paused webhooks can be resumed from the same settings page. The "Recent deliveries" tab shows each attempt and the response code.
