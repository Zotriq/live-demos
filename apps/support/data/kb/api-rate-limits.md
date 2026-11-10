# API rate limits

- The REST API allows 600 requests per minute per workspace on Pro, 3,000 on Enterprise. Starter has no API access.
- Going over the limit returns HTTP 429 with a Retry-After header (seconds). Wait that long, then retry.
- Use the bulk endpoints (/v2/bulk/events) to send up to 500 records per request instead of one call per record.
- Limits reset every minute. Enterprise customers can ask their success manager for a temporary raise.
