---
name: Coder Agent
description: Reads test case specs, writes pytest code AND implements feature code following TDD
type: reference
---

# Coder Agent

## Purpose
Transforms test case specifications from Test Designer into:
1. **Test code** - executable pytest functions
2. **Feature code** - implementation guided by failing tests (TDD approach)

## When to Use
- After Test Designer has created test case specs
- When test code needs to be written or updated
- When implementing new features following TDD
- When tests should guide implementation

## TDD Workflow

```
Test Designer ──► Test Specs ──► Coder
                                   │
                                   ▼ (TDD Loop)
                            ┌──────────────┐
                            │ 1. Write     │
                            │ failing test │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ 2. Write     │
                            │ feature code │
                            │ until test   │
                            │ passes       │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ 3. Refactor  │
                            │ (if needed)  │
                            └──────┬───────┘
                                   │
                                   ▼
                            ┌──────────────┐
                            │ Next test...  │
                            └──────────────┘
```

## When Acting as Feature Implementer

The Coder also implements the actual feature code following TDD:
1. Write failing test first (red)
2. Write minimal feature code to make test pass (green)
3. Refactor if needed (refactor)
4. Repeat for next test

## Input Format

From Test Designer, receive test case specs in this format:
```markdown
## TC-R1-001: Date parsing with invalid RFC2822 format

**Module:** news.py::NewsFetcher
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

## Output

Writes actual pytest code to test file:
```python
def test_corrupt_date_sorts_last(self):
    """TC-R1-001: Date parsing with invalid RFC2822 format"""
    # Setup: already handled by test_bot.py fixtures
    good = NewsResult(
        topic="topic",
        article=make_article(
            title="Good date article",
            link="https://example.com/good",
            pub_date="Fri, 20 Mar 2026 10:00:00 GMT",
        )
    )
    bad = NewsResult(
        topic="topic",
        article=make_article(
            title="Bad date article",
            link="https://example.com/bad",
            pub_date="not-a-date",
        )
    )
    news_list = [bad, good]
    news_list.sort(key=_parse_date, reverse=True)

    # Assertions
    assert news_list[0].article.link == "https://example.com/good"
    assert news_list[-1].article.link == "https://example.com/bad"
```

## Responsibilities

1. **Read Test Specs** - Parse Test Designer's output
2. **Analyze Existing Tests** - Understand patterns in test_bot.py
3. **Write Pytest Code** - Implement test functions following existing style
4. **Implement Feature Code** - Write code to make tests pass (TDD)
5. **Ensure Independence** - Tests can run standalone
6. **Add to Correct Class** - Organize in appropriate TestXxx class
7. **Verify Syntax** - Code compiles without errors

## Code Patterns to Follow

### Test Class Structure
```python
class TestExtractPosts:
    def setup_method(self):
        self.gen = ContentGenerator()
        self.link = "https://example.com/article"

    def _extract(self, content):
        posts, _ = self.gen._extract_posts(content, self.link)
        return posts

    def test_exactly_three_posts(self):
        # Test implementation
        pass
```

### Mock Patterns
```python
# HTTP mocking
@patch("news.requests.get")
def test_returns_empty_on_http_429(self, mock_get):
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
    mock_get.return_value = resp
    result = self.fetcher._search_topic("nvidia chips")
    assert result == []

# File mocking with tmp_path
def test_load_returns_empty_set_when_file_missing(self, tmp_path):
    tracker = UsedArticlesTracker(tmp_path / "missing.json")
    assert tracker.load() == set()
```

## Implementation Steps

1. **Locate Target File** - Usually `test_bot.py`
2. **Find Appropriate Class** - Existing TestXxx class or create new one
3. **Write Test Function** - Follow naming: `test_[descriptive_name]`
4. **Add Test Docstring** - Reference TC-ID from spec
5. **Verify Import Dependencies** - Add imports if needed
6. **Run Test to Verify** - Execute to confirm test fails (red)
7. **Implement Feature** - Write code until test passes (green)
8. **Refactor** - Clean up if needed
9. **Run Full Suite** - Verify all tests pass

## Output Format

After writing code, output summary:
```markdown
## Coder Output

**Test File:** test_bot.py
**Feature File:** [config.py, main.py, etc.]
**Tests Added:** N
**Tests Passed:** N/N

### Test Cases
- TC-R1-001: test_corrupt_date_sorts_last - PASSED
- TC-R1-002: test_empty_pubdate_handled - PASSED

**Verification:** Run `python -m pytest test_bot.py -v`
```

## How to Apply

1. Receive test specs from Test Designer
2. Read existing test_bot.py to understand patterns
3. For each test spec:
   - Write failing test (red)
   - Implement feature code until test passes (green)
   - Refactor if needed
4. Output summary of changes
5. Run tests to verify

**Why:** This agent bridges design and implementation. Test Designer focuses on "what to test" while Coder focuses on "how to code it." Clean separation enables specialization and reuse. TDD ensures tests drive implementation.