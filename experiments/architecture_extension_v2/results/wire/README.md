# Lossless MCP wire records

Each `.json.gz` contains the original complete JSON-RPC transcript and tool result, compressed with gzip level 9 and `mtime=0`. The matching summary JSON in `../` records its uncompressed and compressed SHA-256. Recover it with `gzip -dc <file>.json.gz > <file>.json`; a hash check of the recovered bytes verifies identity. Host request/response traces do not expose agent-internal tool calls.
