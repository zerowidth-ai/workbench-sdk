# Notion Integration Test Setup

This guide explains how to set up a Notion workspace for testing the Notion integration nodes.

## Prerequisites

1. A Notion account (free tier works)
2. Access to create integrations at [notion.so/my-integrations](https://www.notion.so/my-integrations)

## Step 1: Create an Internal Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Configure:
   - **Name**: `Workbench Test Integration`
   - **Associated workspace**: Select your workspace
   - **Capabilities**: Enable all (Read, Update, Insert content)
4. Click **"Submit"**
5. Copy the **Internal Integration Token** (starts with `secret_`)

## Step 2: Create a Test Database

1. In Notion, create a new page called "Workbench Test Workspace"
2. Inside that page, create a **Database - Full page**
3. Name it "TestDatabase"
4. Configure these properties:
   | Property | Type | Options (if applicable) |
   |----------|------|-------------------------|
   | Name | Title | (default) |
   | Status | Select | Active, Inactive, Pending |
   | Count | Number | (default) |

5. Add a few sample entries:
   | Name | Status | Count |
   |------|--------|-------|
   | Test Entry 1 | Active | 10 |
   | Test Entry 2 | Inactive | 20 |
   | Archive Test | Pending | 0 |

## Step 3: Create a Test Page

1. Inside "Workbench Test Workspace", create a regular page called "TestPage"
2. Add some content (paragraphs, headings, etc.) for block tests
3. Note this page's ID for `NOTION_TEST_PAGE_ID`

## Step 4: Share with Integration

**Important**: Notion integrations can only access pages explicitly shared with them.

1. Open "Workbench Test Workspace" page
2. Click **"..."** (menu) → **"Connections"** → **"Add connections"**
3. Select your **"Workbench Test Integration"**
4. This shares the page AND all child pages/databases with the integration

## Step 5: Get IDs

### Database ID
1. Open the TestDatabase in Notion
2. The URL will look like: `https://notion.so/workspace/abc123def456...?v=...`
3. The database ID is the 32-character string before `?v=`
4. Format with dashes: `abc123de-f456-7890-abcd-ef1234567890`

### Page IDs
1. Open TestPage or any database entry
2. Get the ID from the URL the same way
3. For `NOTION_TEST_PAGE_TO_ARCHIVE`, use the "Archive Test" entry's ID

## Step 6: Set Environment Variables

Add to `sdks/nodejs/.env` and `sdks/python/.env`:

```bash
# Notion Integration
NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TEST_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_TEST_PAGE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_TEST_PAGE_TO_ARCHIVE=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

## Running Tests

```bash
# Node.js
cd sdks/nodejs
node tests/test.all-nodes.js --node notion-query-database
node tests/test.all-nodes.js --node notion-search

# Python
cd sdks/python
python tests/test_all_nodes.py --node notion-query-database
python tests/test_all_nodes.py --node notion-search
```

## API Reference

- [Notion API Documentation](https://developers.notion.com/reference/intro)
- [Working with Databases](https://developers.notion.com/docs/working-with-databases)
- [Block Types](https://developers.notion.com/reference/block)

## Notes

- Notion's API version is pinned to `2022-06-28` in the integration
- Rate limits: 3 requests/second per integration
- Page/database IDs can be with or without dashes (the API accepts both)
- Archived pages can be restored by setting `archived: false`
