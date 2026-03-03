# Airtable Test Setup Guide

Configuration needed to run Airtable integration tests.

## 1. Create Personal Access Token

1. Go to [airtable.com/create/tokens](https://airtable.com/create/tokens)
2. Create token with scopes: `data.records:read`, `data.records:write`
3. Copy the token (starts with `pat...`)

## 2. Create Test Base & Table

Create a base with a table called `TestTable`:

| Field Name | Type | Required |
|------------|------|----------|
| `Name` | Single line text | Yes (primary) |
| `Status` | Single select | Yes |
| `Count` | Number | No |

**Status options:** `Active`, `Inactive`

Add 2-3 sample records so list/filter tests have data to work with.

## 3. Get IDs

From your base URL `https://airtable.com/appXXX/tblYYY/...`:
- Base ID: `appXXX...`
- Table: Use name `TestTable` or ID `tblYYY...`
- Record ID: Click a record, copy ID from URL (starts with `rec...`)

## 4. Environment Variables

Add to `.env`:

```bash
# Airtable API Key
AIRTABLE_API_KEY=patXXXXXXXXXXXXXXXXXXXXXX

# Test table configuration
AIRTABLE_TEST_BASE_ID=appXXXXXXXXXXXXXX
AIRTABLE_TEST_TABLE_NAME=TestTable

# For get/update tests - ID of an existing record
AIRTABLE_TEST_RECORD_ID=recXXXXXXXXXXXXXX

# For delete test - create a throwaway record and put its ID here
AIRTABLE_TEST_RECORD_TO_DELETE=recYYYYYYYYYYYYYY
```

## 5. Test Behaviors

Tests use special flags:
- `skipIfIntegration: "airtable"` - Runs only when NO API key configured (error case)
- `requiresIntegration: "airtable"` - Runs only when API key IS configured (functional tests)

### Test Coverage

| Node | Tests |
|------|-------|
| `airtable-list-records` | List all, filter by Status, sort by Name, limit with max_records |
| `airtable-get-record` | Get by ID, error on invalid ID |
| `airtable-create-record` | Create minimal, create with all fields, typecast |
| `airtable-update-record` | Update one field, update multiple, error on invalid ID |
| `airtable-delete-record` | Delete existing, error on invalid ID |

## 6. Running Tests

```bash
# Without API key - only error tests run
node tests/test.all-nodes.js --node airtable-list-records

# With API key configured - functional tests run
AIRTABLE_API_KEY=pat... node tests/test.all-nodes.js --node airtable-list-records
```

## Notes

- Free tier: 5 requests/second rate limit
- Create tests will add records to your table (clean up periodically)
- Delete test needs a fresh record ID each run
- Consider a dedicated "CI Test" base to avoid polluting real data
