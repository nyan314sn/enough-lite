# Attack results

Run against http://127.0.0.1:8074

| Category | Cases | Pass | Fail |
|---|---|---|---|
| overspending | 1 | 0 | 1 |
| **total** | 1 | 0 | 1 |

## Failures

- OS-05 (overspending): http_ok: status codes [0, 200] ('TimeoutError: timed out'); spend $0.0875 of $0.50 cap
