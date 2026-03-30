---
name: Test Coder Agent
description: Transforms test case specs from Test Designer into executable pytest code
type: reference
---

# Test Coder Agent

## Purpose
One job: take test case specs from the Test Designer and write working pytest
code. Does not implement feature code — that belongs to the Feature Implementer.
Does not design tests — that belongs to the Test Designer.

The split matters because test code and feature code have different failure modes,
different reviewers, and different retry strategies. Bundling them creates a leaky
abstraction where you cannot invoke "just the test writer" cleanly.

## When to Use
- Phase.TEST_CODE — after Test Designer completes
- When rewinding from a `test_bug` FeedbackEvent (test code was wrong)
- When test specs are updated and existing tests need revision

## Inputs

From `PipelineState`:
```python
state.get_artifact(ArtifactKey.TEST_SUITE_MANIFEST)   # from Test Designer
state.get_artifact(ArtifactKey.CODEBASE_SNAPSHOT)     # to understand existing test patterns
```

## Output Artifact

```python
state.set_artifact(ArtifactKey.TEST_FILE_PATH, {
    "path": "test_bot.py",
    "tests_added": 8,
    "test_ids": ["TC-R1-001", "TC-R1-002", "TC-S1-001"],
    "classes_modified": ["TestDateSorting", "TestNewsFetcher"],
})
```

## Responsibilities

1. Read existing test file to understand conventions before writing anything
2. For each test case spec, write one `test_` function
3. Place it in the correct `TestXxx` class (create the class if needed)
4. Ensure each test is independently runnable
5. Verify syntax compiles — run `python -m py_compile test_bot.py`
6. Do **not** run the tests — that is Test Executor's job
7. Do **not** modify feature code — flag it via `state.record_error()` if needed

## Reading Existing Patterns First

Before writing a single line, read the target test file and identify:
- Fixture patterns (`setup_method`, `tmp_path`, `@pytest.fixture`)
- Mock patterns (`@patch`, `MagicMock`, context managers)
- Helper methods (`_extract()`, `make_article()`, etc.)
- Import block — what is already imported

Inconsistent test style is a maintenance debt. Match what exists.

## Input Format

From Test Designer:
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

## Output: Pytest Code

```python
class TestDateSorting:
    """Tests for date-based article ordering — Risk R1."""

    def test_corrupt_date_sorts_last(self):
        """TC-R1-001: Date parsing with invalid RFC2822 format."""
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

        assert news_list[0].article.link == "https://example.com/good"
        assert news_list[-1].article.link == "https://example.com/bad"
```

## Code Patterns

### Test Class Structure
```python
class TestExtractPosts:
    def setup_method(self):
        self.gen = ContentGenerator()
        self.link = "https://example.com/article"

    def _extract(self, content):           # shared helper — reduces duplication
        posts, _ = self.gen._extract_posts(content, self.link)
        return posts

    def test_exactly_three_posts(self):
        pass
```

### HTTP Mocking
```python
@patch("news.requests.get")
def test_returns_empty_on_http_429(self, mock_get):
    resp = MagicMock()
    resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
    mock_get.return_value = resp
    result = self.fetcher._search_topic("nvidia chips")
    assert result == []
```

### File Mocking
```python
def test_load_returns_empty_set_when_file_missing(self, tmp_path):
    tracker = UsedArticlesTracker(tmp_path / "missing.json")
    assert tracker.load() == set()
```

### Exception Assertion
```python
def test_invalid_config_raises_value_error(self):
    with pytest.raises(ValueError, match="RSS_FEED_URL"):
        Config(rss_feed_url="")
```

## Naming Conventions

| Pattern | Example |
|---------|---------|
| Test function | `test_[behaviour_under_test]` |
| Docstring | TC-ID on first line |
| Class | `Test[ModuleOrConcept]` |
| Helper | `_[descriptive_name]` |

## FeedbackEvent on Failure

If this agent is re-invoked via a `test_bug` rewind, it receives context about
which tests failed and why. It should fix only the failing tests — do not
regenerate the entire file.

```python
# Test Executor added this before rewinding
FeedbackEvent(
    test_id="TC-R1-001",
    failure_type="test_bug",
    detail="AttributeError: 'NewsResult' has no attribute 'article'",
    target_phase=Phase.TEST_CODE,
)
```

The agent reads pending feedback from state before writing:
```python
feedback = state.consume_feedback("test_bug")
# fix only the affected test IDs
```

## Output Summary

```markdown
## Test Coder Output

**Test File:** test_bot.py
**Tests Added:** 8
**Classes Modified:** TestDateSorting (new), TestNewsFetcher (extended)
**Syntax Check:** PASSED (py_compile)

### Test Cases Written
- TC-R1-001: test_corrupt_date_sorts_last
- TC-R1-002: test_empty_pubdate_sorts_last
- TC-S1-001: test_path_traversal_blocked
- TC-S1-002: test_path_traversal_dotdot
- TC-R2-001: test_http_429_returns_empty
- TC-R2-002: test_http_timeout_returns_empty
- TC-T1-001: test_config_missing_url_raises
- TC-T1-002: test_config_missing_token_raises

**Next:** Feature Implementer (Phase.FEATURE_CODE)
```

**Why:** Separating test writing from feature implementation keeps each agent
focused on one failure mode. A broken test and a broken feature require
different fixes — routing them through the same agent forces false coupling.
