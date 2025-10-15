### Console Output Examples

The examples below mirror the CLI output format produced by `skuld sync`.

1) Preview (`--test` dry-run)

```bash
Worklog Preview (dry-run)
Period: 2025-10-15T08:00:00 → 2025-10-15T17:30:00
-----------------------------------------------------------------------------------------
Issue: SOT-507
Name:  Add migration for unique, indexed slug for Company
Status: To Do
Next: Will transition to 'In Progress' on upload.
Time to add:  3m 55s
Total Time: 19m 45s
Already Logged: 15m 50s
Comment:
  [SKULD] - Adding `3m 55s` on `15/10/25` at `11:33 AM`  
  - Merged in feature/SOT-507-public-identifier-for-company (pull request #208)
-----------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------
Issue: SOT-607
Name:  Plot sites on the map
Status: In Progress
Time to add:  1h 30m
Total Time: 4h 34m 12s
Comment:
  [SKULD] - Adding `1h 30m` on `15/10/25` at `11:33 AM`  
  - Added arm state to sites on map
  - Added ability to do multi base-station select
-----------------------------------------------------------------------------------------
```

2) Upload ("prod" mode)

```bash
Transitioned SOT-507 → In Progress
Upload summary:
  + SOT-507: 3m 55s (worklog 12345, comment 67890)
  - SOT-607: skipped (no_delta)
```
