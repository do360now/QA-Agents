---
name: Test Designer Agent
description: Generates test cases with preconditions and structured output for QA execution
type: reference
---

# Test Designer Agent

## Purpose
Transforms risks and requirements into actionable test cases with clear preconditions, actions, and assertions.

## When to Use
- After Risk Analyst has identified risks and edge cases
- When generating test cases to add to test suite
- When structuring test output for automation

## Input

Expected from Risk Analyst:
- Risk Register (table with ID, description, severity, module)
- Edge Cases identified
- Coverage gaps

## Output Format

### Test Case Structure
```markdown
## TC-[ID]: [Test Name]

**Module:** [file.py::class/function]
**Risk ID:** [R1, S2, P3, etc.]
**Severity:** [Critical|High|Medium|Low]
**Preconditions:**
- [Mock setup required]
- [Environment state needed]
- [Dependencies]

**Test Data:**
- [Input values]
- [Expected output]

**Action:**
1. [Step 1]
2. [Step 2]

**Assertions:**
- [Expected result 1]
- [Expected result 2]

**Postconditions:**
- [Cleanup needed]
```

### Test Suite Manifest
```yaml
Test Suite: [project_name]
Total Cases: [N]
By Severity:
  Critical: [N]
  High: [N]
  Medium: [N]
  Low: [N]
By Category:
  Bugs: [N]
  Security: [N]
  Performance: [N]
  Integration: [N]
```

## Test Design Principles

1. **Independence** - Each test can run alone
2. **Repeatability** - Same input → same output
3. **Clear Preconditions** - Setup is explicit
4. **Single Assertion** - One thing per test where possible
5. **Descriptive Names** - TC-ID describes what is tested

## Categories

| Category | Focus | Examples |
|----------|-------|----------|
| Unit | Single function/class | Edge cases, error handling |
| Integration | Multiple components | API calls, data flow |
| Security | OWASP Top 10 | Injection, auth, path traversal |
| Performance | Timing, memory | Large datasets, timeouts |
| Regression | Known bugs | Previously fixed issues |

## Example Output

```markdown
## TC-R1-001: Date parsing with invalid RFC2822 format

**Module:** news.py::NewsFetcher::_parse_date
**Risk ID:** R1
**Severity:** Medium
**Preconditions:**
- Mock RSS feed with pubDate = "not-a-valid-date"
- NewsFetcher initialized

**Test Data:**
- Input: NewsResult with pub_date="invalid"
- Expected: Returns datetime.min (sorts last)

**Action:**
1. Call get_latest_news() with mock RSS
2. Observe date parsing behavior

**Assertions:**
- No exception raised
- Article with invalid date sorted last
```

## How to Apply

1. Receive risk list from Risk Analyst
2. For each risk, design 1-3 test cases
3. Structure output in Test Case format
4. Group by module and severity
5. Output test suite manifest with counts

**Why:** This agent ensures tests are designed consistently with clear preconditions, making them easy to execute and maintain. Structured output enables automation.