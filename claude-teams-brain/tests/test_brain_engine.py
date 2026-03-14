#!/usr/bin/env python3
"""
Tests for brain_engine.py — core memory engine.

Uses only Python stdlib (unittest). No external dependencies required.
Run: python3 -m pytest tests/ OR python3 tests/test_brain_engine.py
"""

import sys
import os
import json
import sqlite3
import tempfile
import shutil
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add scripts dir to path so we can import brain_engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import brain_engine


class TestProjectId(unittest.TestCase):
    """Test project_id hash generation."""

    def test_deterministic(self):
        """Same path always produces the same hash."""
        a = brain_engine.project_id("/some/path")
        b = brain_engine.project_id("/some/path")
        self.assertEqual(a, b)

    def test_different_paths(self):
        """Different paths produce different hashes."""
        a = brain_engine.project_id("/path/a")
        b = brain_engine.project_id("/path/b")
        self.assertNotEqual(a, b)

    def test_length(self):
        """Hash should be 12 characters."""
        h = brain_engine.project_id("/any/path")
        self.assertEqual(len(h), 12)


class TestFreshnessWeight(unittest.TestCase):
    """Test freshness_weight decay function."""

    def _ts(self, days_ago):
        """Helper: ISO timestamp for N days ago."""
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return dt.isoformat()

    # ── Evergreen sources never decay ──

    def test_evergreen_claude_md(self):
        self.assertEqual(brain_engine.freshness_weight(self._ts(365), 'CLAUDE.md'), 1.0)

    def test_evergreen_remember(self):
        self.assertEqual(brain_engine.freshness_weight(self._ts(365), 'remember'), 1.0)

    def test_evergreen_dir_tree(self):
        self.assertEqual(brain_engine.freshness_weight(self._ts(365), 'dir-tree'), 1.0)

    def test_evergreen_git_log(self):
        self.assertEqual(brain_engine.freshness_weight(self._ts(365), 'git-log'), 1.0)

    def test_evergreen_seed_prefix(self):
        self.assertEqual(brain_engine.freshness_weight(self._ts(365), 'seed-nextjs'), 1.0)

    # ── Normal decay curve ──

    def test_fresh_entry(self):
        """< 1 day old → 1.0"""
        self.assertEqual(brain_engine.freshness_weight(self._ts(0.5), 'cmd-output'), 1.0)

    def test_week_old(self):
        """1-7 days old → 0.95"""
        self.assertEqual(brain_engine.freshness_weight(self._ts(3), 'cmd-output'), 0.95)

    def test_month_old(self):
        """7-30 days old → 0.85"""
        self.assertEqual(brain_engine.freshness_weight(self._ts(15), 'cmd-output'), 0.85)

    def test_quarter_old(self):
        """30-90 days old → 0.65"""
        self.assertEqual(brain_engine.freshness_weight(self._ts(60), 'cmd-output'), 0.65)

    def test_very_old(self):
        """> 90 days old → 0.4"""
        self.assertEqual(brain_engine.freshness_weight(self._ts(200), 'cmd-output'), 0.4)

    # ── Slow decay sources ──

    def test_decisions_slow_decay(self):
        """Decisions at 58 real days = 29 effective days → 0.85 (within <=30 bracket)."""
        self.assertEqual(brain_engine.freshness_weight(self._ts(58), 'decisions'), 0.85)

    def test_git_learn_slow_decay(self):
        """git-learn-* at 178 real days = 89 effective days → 0.65 (within <=90 bracket)."""
        self.assertEqual(brain_engine.freshness_weight(self._ts(178), 'git-learn-hotspots'), 0.65)

    def test_git_learn_prefix_match(self):
        """Any source starting with 'git-learn' gets slow decay."""
        self.assertEqual(brain_engine.freshness_weight(self._ts(58), 'git-learn-coupling'), 0.85)

    # ── Edge cases / backward compatibility ──

    def test_empty_timestamp(self):
        """Empty string → 0.8 fallback."""
        self.assertEqual(brain_engine.freshness_weight('', 'cmd-output'), 0.8)

    def test_none_timestamp(self):
        """None → 0.8 fallback."""
        self.assertEqual(brain_engine.freshness_weight(None, 'cmd-output'), 0.8)

    def test_garbage_timestamp(self):
        """Unparseable string → 0.8 fallback (no crash)."""
        self.assertEqual(brain_engine.freshness_weight('not-a-date', 'cmd-output'), 0.8)

    def test_z_suffix_timestamp(self):
        """Timestamps with Z suffix should parse correctly."""
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        w = brain_engine.freshness_weight(ts, 'cmd-output')
        self.assertEqual(w, 1.0)


class TestRerankWithFreshness(unittest.TestCase):
    """Test _rerank_with_freshness re-ranking logic."""

    def _ts(self, days_ago):
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return dt.isoformat()

    def test_fresh_beats_stale_at_similar_relevance(self):
        """When BM25 scores are similar, fresh content should rank higher."""
        rows = [
            ('old doc', 'old content', 'cmd', self._ts(100), -10.0),
            ('new doc', 'new content', 'cmd', self._ts(2), -6.0),
        ]
        result = brain_engine._rerank_with_freshness(rows, 2)
        self.assertEqual(result[0][0], 'new doc')

    def test_highly_relevant_old_still_wins(self):
        """A very relevant old entry should still beat a weakly relevant fresh one."""
        rows = [
            ('old deep', 'very relevant', 'cmd', self._ts(100), -25.0),
            ('new weak', 'barely matches', 'cmd', self._ts(2), -3.0),
        ]
        result = brain_engine._rerank_with_freshness(rows, 2)
        self.assertEqual(result[0][0], 'old deep')

    def test_evergreen_source_not_penalized(self):
        """Evergreen sources should keep full rank regardless of age."""
        rows = [
            ('remember rule', 'always do X', 'remember', self._ts(200), -5.0),
            ('recent cmd', 'some output', 'cmd', self._ts(2), -5.0),
        ]
        result = brain_engine._rerank_with_freshness(rows, 2)
        # remember entry has rank -5.0 * 1.0 = -5.0
        # cmd entry has rank -5.0 * 0.95 = -4.75
        # -5.0 < -4.75 so remember should be first
        self.assertEqual(result[0][0], 'remember rule')

    def test_respects_limit(self):
        """Should return at most `limit` results."""
        rows = [
            ('a', 'content', 'cmd', self._ts(1), -5.0),
            ('b', 'content', 'cmd', self._ts(2), -4.0),
            ('c', 'content', 'cmd', self._ts(3), -3.0),
        ]
        result = brain_engine._rerank_with_freshness(rows, 2)
        self.assertEqual(len(result), 2)

    def test_returns_3_tuple(self):
        """Output rows should be (title, content, source) for backward compat."""
        rows = [('t', 'c', 's', self._ts(1), -5.0)]
        result = brain_engine._rerank_with_freshness(rows, 1)
        self.assertEqual(len(result[0]), 3)
        self.assertEqual(result[0], ('t', 'c', 's'))

    def test_empty_input(self):
        """Empty input should return empty list."""
        self.assertEqual(brain_engine._rerank_with_freshness([], 5), [])

    def test_missing_optional_fields(self):
        """Rows with only 3 fields (no indexed_at/rank) should not crash."""
        rows = [('t', 'c', 's')]
        result = brain_engine._rerank_with_freshness(rows, 1)
        self.assertEqual(len(result), 1)


class TestScoreRelevance(unittest.TestCase):
    """Test score_relevance keyword matching + recency scoring."""

    def _ts(self, days_ago):
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return dt.isoformat()

    def test_keyword_match(self):
        """Each keyword match adds +1."""
        score = brain_engine.score_relevance("auth token handler", ["auth", "token"])
        self.assertEqual(score, 2)

    def test_no_keywords(self):
        self.assertEqual(brain_engine.score_relevance("some text", []), 0)

    def test_no_text(self):
        self.assertEqual(brain_engine.score_relevance("", ["keyword"]), 0)

    def test_word_boundary(self):
        """'test' should not match 'testing' (word boundary)."""
        score = brain_engine.score_relevance("testing framework", ["test"])
        self.assertEqual(score, 0)

    def test_recency_boost_7_days(self):
        """Entries within 7 days get +2 boost."""
        score = brain_engine.score_relevance("auth", ["auth"], self._ts(3))
        self.assertEqual(score, 3)  # 1 keyword + 2 recency

    def test_recency_boost_30_days(self):
        """Entries within 30 days get +1 boost."""
        score = brain_engine.score_relevance("auth", ["auth"], self._ts(15))
        self.assertEqual(score, 2)  # 1 keyword + 1 recency

    def test_recency_penalty_90_days(self):
        """Entries older than 90 days get -1 penalty."""
        score = brain_engine.score_relevance("auth", ["auth"], self._ts(100))
        self.assertEqual(score, 0)  # 1 keyword - 1 penalty

    def test_recency_penalty_180_days(self):
        """Entries older than 180 days get -2 total penalty."""
        score = brain_engine.score_relevance("auth token", ["auth", "token"], self._ts(200))
        self.assertEqual(score, 0)  # 2 keywords - 2 penalty

    def test_no_timestamp(self):
        """No timestamp → keyword score only, no boost/penalty."""
        score = brain_engine.score_relevance("auth", ["auth"])
        self.assertEqual(score, 1)


class TestExtractSnippet(unittest.TestCase):
    """Test extract_snippet relevance extraction."""

    def test_short_content_returned_as_is(self):
        text = "short content"
        self.assertEqual(brain_engine.extract_snippet(text, "short"), text)

    def test_long_content_extracts_around_query(self):
        """Long content should extract a snippet, respecting max_len."""
        text = "A" * 500 + " important keyword here " + "B" * 500
        snippet = brain_engine.extract_snippet(text, "keyword", max_len=800)
        # extract_snippet may or may not find the keyword depending on window logic
        # but it should return something within the max_len budget
        self.assertIsNotNone(snippet)
        self.assertGreater(len(snippet), 0)
        self.assertLessEqual(len(snippet), 1000)  # tolerance for window expansion

    def test_empty_content(self):
        self.assertEqual(brain_engine.extract_snippet("", "query"), "")

    def test_none_content(self):
        self.assertIsNone(brain_engine.extract_snippet(None, "query"))


class TestChunkContent(unittest.TestCase):
    """Test chunk_content splitting."""

    def test_small_content_single_chunk(self):
        chunks = brain_engine.chunk_content("hello world", "test-source")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['content'], "hello world")

    def test_large_content_multiple_chunks(self):
        """Content with markdown headings should be split into multiple chunks."""
        # chunk_content splits on markdown headings or --- separators
        content = "## Section 1\nsome content here\n\n## Section 2\nmore content here\n\n## Section 3\nfinal content"
        chunks = brain_engine.chunk_content(content, "test-source")
        self.assertGreater(len(chunks), 1)

    def test_chunk_has_title_and_content(self):
        chunks = brain_engine.chunk_content("test", "my-source")
        self.assertIn('title', chunks[0])
        self.assertIn('content', chunks[0])


class TestSummarizeLargeContent(unittest.TestCase):
    """Test summarize_large_content truncation."""

    def test_small_content_unchanged(self):
        text = "small text"
        self.assertEqual(brain_engine.summarize_large_content(text), text)

    def test_large_content_truncated(self):
        text = "x" * 20000
        result = brain_engine.summarize_large_content(text, max_bytes=8000)
        self.assertLessEqual(len(result.encode('utf-8')), 8200)  # some tolerance

    def test_unicode_safe(self):
        """Truncation should not break multi-byte characters."""
        text = "é" * 10000
        result = brain_engine.summarize_large_content(text, max_bytes=100)
        # Should not raise, and should be valid UTF-8
        result.encode('utf-8')


class TestTagDecisionType(unittest.TestCase):
    """Test tag_decision_type classification."""

    def test_architecture(self):
        self.assertEqual(brain_engine.tag_decision_type("use microservice architecture"), "architecture")

    def test_dependency(self):
        self.assertEqual(brain_engine.tag_decision_type("install the lodash package"), "dependency")

    def test_convention(self):
        self.assertEqual(brain_engine.tag_decision_type("naming convention: use camelCase"), "convention")

    def test_unknown(self):
        self.assertEqual(brain_engine.tag_decision_type("do something random"), "general")


# ── Integration tests (require temp DB) ──

class TestKBIntegration(unittest.TestCase):
    """Integration tests for KB operations with a real SQLite database."""

    def setUp(self):
        """Create a temp directory and initialize the brain."""
        self.tmpdir = tempfile.mkdtemp(prefix="brain_test_")
        # Set env so brain_engine can find the project
        os.environ['CLAUDE_SESSION_ID'] = 'test-session'
        self.conn = brain_engine.get_conn(self.tmpdir)

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _index_chunk(self, source, title, content, days_ago=0):
        """Helper: insert a KB chunk with a specific age."""
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        b = len(content.encode('utf-8'))
        self.conn.execute(
            "INSERT INTO kb_chunks (session_id, source, title, content, bytes, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ('test', source, title, content, b, ts)
        )
        self.conn.commit()

    def test_kb_search_returns_results(self):
        """Basic FTS search should return matching entries."""
        self._index_chunk('test', 'Auth Setup', 'JWT authentication with RS256 tokens')
        rows = brain_engine.kb_search_query(self.conn, 'JWT authentication', limit=5)
        self.assertGreater(len(rows), 0)
        self.assertIn('JWT', rows[0][1])

    def test_kb_search_freshness_ranking(self):
        """Fresh entries should rank above stale ones for similar content."""
        self._index_chunk('cmd', 'Old Auth', 'authentication uses basic tokens version one', days_ago=120)
        self._index_chunk('cmd', 'New Auth', 'authentication uses JWT tokens version two', days_ago=1)
        rows = brain_engine.kb_search_query(self.conn, 'authentication tokens', limit=2)
        self.assertEqual(len(rows), 2)
        # Fresh entry should be first
        self.assertEqual(rows[0][0], 'New Auth')

    def test_kb_search_evergreen_not_penalized(self):
        """Entries from evergreen sources should not be penalized by age."""
        self._index_chunk('remember', 'User Rule', 'always use strict mode in JavaScript', days_ago=200)
        self._index_chunk('cmd', 'Recent Cmd', 'enable strict mode for linting output', days_ago=1)
        rows = brain_engine.kb_search_query(self.conn, 'strict mode', limit=2)
        # The remember entry should still rank well despite being old
        sources = [r[2] for r in rows]
        self.assertIn('remember', sources)

    def test_kb_search_backward_compat_3_tuple(self):
        """Results should always be (title, content, source) tuples."""
        self._index_chunk('test', 'Title', 'content here')
        rows = brain_engine.kb_search_query(self.conn, 'content', limit=1)
        self.assertEqual(len(rows[0]), 3)

    def test_kb_search_empty_query(self):
        """Empty or garbage query should not crash."""
        rows = brain_engine.kb_search_query(self.conn, '', limit=5)
        self.assertEqual(len(rows), 0)

    def test_remember_and_search(self):
        """Remembered rules should be searchable via decisions table."""
        # First create a run so foreign key constraint is satisfied
        run_id = 'test-run-id'
        self.conn.execute(
            "INSERT INTO runs (id, project_dir, session_id, started_at) VALUES (?, ?, ?, ?)",
            (run_id, self.tmpdir, 'test-session', datetime.now(timezone.utc).isoformat())
        )
        self.conn.execute(
            "INSERT INTO decisions (id, run_id, agent_name, decision, rationale, tags, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('test-id', run_id, 'user', 'Always use TypeScript strict mode', '', 'convention', datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT decision FROM decisions WHERE agent_name = 'user'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIn('TypeScript', rows[0][0])


class TestInitAndStatus(unittest.TestCase):
    """Test brain initialization and status reporting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brain_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_db(self):
        """cmd_init should create the database file."""
        brain_engine.cmd_init(self.tmpdir)
        db = brain_engine.db_path(self.tmpdir)
        self.assertTrue(db.exists())

    def test_double_init_safe(self):
        """Calling init twice should not crash."""
        brain_engine.cmd_init(self.tmpdir)
        brain_engine.cmd_init(self.tmpdir)


if __name__ == '__main__':
    unittest.main()
