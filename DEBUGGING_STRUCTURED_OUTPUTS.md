# Debugging Structured Outputs

## Overview

All Claude Agent SDK responses (successful and failed) are automatically logged to `logs/agent_responses/` for auditing and debugging.

## Common Failure Reasons

### 1. Empty Response ("Expecting value: line 1 column 1")

**Possible Causes:**
- **Schema too complex**: Claude's grammar compiler has limits. Very deep nesting or many properties can fail.
- **Model refusal**: Claude refused to respond (safety/content policy).
- **Token limit**: Response was cut off before any JSON was generated.

**How to Debug:**
1. Check the log file path in the error message
2. Look at `stop_reason` in the log:
   - `"max_tokens"` → Response was truncated, schema might be too large
   - `"refusal"` → Claude refused the request
   - `null` or other → Schema compilation or other issue

**Solutions:**
- Simplify your schema (fewer fields, less nesting)
- Break into multiple smaller queries
- Check if your prompt triggers safety filters

### 2. Invalid JSON

**Possible Causes:**
- Markdown code fences in response (shouldn't happen with `output_format`)
- Partial response (truncated)
- SDK version incompatibility

**How to Debug:**
1. Check the log file's `raw_response` field
2. Look for markdown fences: ` ```json `
3. Check if response is incomplete (ends mid-object)

**Solutions:**
- The logging now captures this automatically
- Report to the team with the log file

### 3. Schema Validation Errors

**Possible Causes:**
- Schema has unsupported features (see below)
- `additionalProperties` not set to `false`
- Recursive schemas

**How to Debug:**
1. Check the error message for specific field violations
2. Review your Pydantic model against supported features

**Solutions:**
- Ensure all objects have `additionalProperties = False`
- Avoid recursive schemas
- Use simpler data types

## Supported JSON Schema Features

✅ **Supported:**
- Basic types: object, array, string, integer, number, boolean, null
- `enum` (primitives only)
- `const`
- `anyOf` and `allOf` (limited)
- `required` fields
- String formats: date-time, email, uri, uuid, etc.

❌ **Not Supported:**
- Numerical constraints (minimum, maximum)
- String length constraints (minLength, maxLength)
- Recursive schemas
- Complex types in enums
- External `$ref`

## Log File Format

Each response is saved to `logs/agent_responses/response_YYYYMMDD_HHMMSS_microseconds.json`:

```json
{
  "timestamp": "20260206_143022_123456",
  "repo_path": "/path/to/repo",
  "schema": "APIDocumentation",
  "query_length": 1234,
  "response_length": 5678,
  "stop_reason": "end_turn",
  "raw_response": "...the actual response...",
  "success": true,
  "error": "error message if failed"
}
```

## Inspecting Logs

```bash
# View most recent log
ls -t logs/agent_responses/ | head -1 | xargs -I {} cat "logs/agent_responses/{}"

# View all failed responses
find logs/agent_responses/ -name "*.json" -exec grep -l '"success": false' {} \;

# Count success vs failures
echo "Successful: $(grep -l '"success": true' logs/agent_responses/*.json | wc -l)"
echo "Failed: $(grep -l '"success": false' logs/agent_responses/*.json | wc -l)"
```

## Best Practices

1. **Start Simple**: Test with a minimal schema first
2. **Check Logs**: Always check the log file when debugging
3. **Iterate**: If a complex schema fails, try breaking it into parts
4. **Monitor**: Keep an eye on the logs directory size

## Example: Simplifying a Complex Schema

If your API analysis is failing, try:

**Option 1: Analyze fewer endpoints**
- Add filtering logic to only analyze certain routes
- Process in batches

**Option 2: Simplify the schema**
- Remove optional fields
- Reduce nesting depth
- Use simpler types (string instead of complex objects)

**Option 3: Multiple queries**
- Query for endpoint list first
- Then query each endpoint individually
