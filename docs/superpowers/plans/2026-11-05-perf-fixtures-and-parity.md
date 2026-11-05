# Performance fixtures and feature parity implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate checksummed workload profiles and named feature profiles so two trials can be compared only when they name the same work and the same features.

**Architecture:** `perf/fixtures/generate.py` writes small deterministic byte strings and their SHA-256. It does not write multi-gigabyte files in unit tests. `perf/fixtures/profiles.py` names the size ladder and the P0–P3 feature sets. Later plans pass `workload_id` and `feature_profile` into the environment record from Plan 1.

**Tech Stack:** Python 3, `hashlib`, `unittest`.

## Global Constraints

- Do not modify `repos/` or `fixture/complex.docx`.
- Do not commit generated multi-gigabyte files. Tests use profiles whose `max_test_bytes` is under 4096.
- A workload records paragraph shape, Unicode class, and, for search profiles, the match count.
- Feature fallback is data on the profile, not a silent change of P0 into a faster editor.
- Hostile-package paths are rejected by `assert_not_hostile`.
- Coverage ids owned here: C02 C06 C08 C13 C14 C15 C21 C22 I01 I02 I03 I04 I05 I06.

---

### Task 1: Deterministic workload bytes

**Files:**
- Create: `perf/fixtures/__init__.py`
- Create: `perf/fixtures/generate.py`
- Test: `perf/tests/test_fixtures.py`

**Interfaces:**
- Consumes: nothing
- Produces: `build_workload(profile: dict) -> dict` with keys `workload_id`, `sha256`, `body` (`bytes`), `paragraphs`, `unicode_class`, `match_count`

- [ ] **Step 1: Write the failing test**

```python
import unittest

from perf.fixtures.generate import build_workload


SHORT = {
    "workload_id": "short-paragraphs",
    "paragraphs": 3,
    "paragraph_chars": 5,
    "unicode_class": "ascii",
    "match_count": 0,
    "seed": 1,
}


class BuildWorkload(unittest.TestCase):
    def test_same_profile_same_hash(self):
        first = build_workload(SHORT)
        second = build_workload(SHORT)
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(len(first["sha256"]), 64)
        self.assertEqual(first["body"].count(b"\n"), 3)

    def test_more_paragraphs_change_the_hash(self):
        other = dict(SHORT, paragraphs=4)
        self.assertNotEqual(build_workload(SHORT)["sha256"], build_workload(other)["sha256"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_fixtures.BuildWorkload -v`

Expected: ERROR containing `ModuleNotFoundError: No module named 'perf.fixtures'`

- [ ] **Step 3: Write the minimal implementation**

`perf/fixtures/__init__.py` is empty.

`perf/fixtures/generate.py`:

```python
import hashlib


def build_workload(profile):
    paragraphs = int(profile["paragraphs"])
    width = int(profile["paragraph_chars"])
    if paragraphs < 1 or width < 1:
        raise ValueError("workload shape")
    if profile["unicode_class"] != "ascii":
        raise ValueError("unicode_class")
    lines = []
    for index in range(paragraphs):
        piece = ("p%02d" % index).encode("ascii")
        piece = (piece * (width // len(piece) + 1))[:width]
        lines.append(piece)
    body = b"\n".join(lines) + b"\n"
    return {
        "workload_id": profile["workload_id"],
        "sha256": hashlib.sha256(body).hexdigest(),
        "body": body,
        "paragraphs": paragraphs,
        "unicode_class": profile["unicode_class"],
        "match_count": int(profile["match_count"]),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_fixtures.BuildWorkload -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/fixtures/__init__.py perf/fixtures/generate.py perf/tests/test_fixtures.py
git commit -m "test: hash deterministic short performance workloads"
```

---

### Task 2: Unicode, emoji, bidi, and IME fixtures

**Files:**
- Modify: `perf/fixtures/generate.py`
- Modify: `perf/tests/test_fixtures.py`

**Interfaces:**
- Consumes: `build_workload`
- Produces: `correctness_fixtures() -> dict[str, bytes]` with keys `unicode`, `emoji`, `bidi`, and `ime_committed`. The emoji value contains the family sequence `👨‍👩‍👧‍👦` and the skin-tone scalar `👍🏻`. The bidi value contains `Hello` and `مرحبا`. The IME value is the committed string `地` and does not contain the intermediate `di`.

- [ ] **Step 1: Write the failing test**

```python
from perf.fixtures.generate import correctness_fixtures


class CorrectnessFixtures(unittest.TestCase):
    def test_unicode_keeps_a_combining_mark_and_a_non_bmp_scalar(self):
        body = correctness_fixtures()["unicode"].decode("utf-8")
        self.assertIn("e\u0301", body)
        self.assertIn("𠀋", body)

    def test_emoji_fixture_contains_zwj_family_and_skin_tone(self):
        body = correctness_fixtures()["emoji"].decode("utf-8")
        self.assertIn("👨‍👩‍👧‍👦", body)
        self.assertIn("👍🏻", body)

    def test_bidi_fixture_keeps_logical_order(self):
        body = correctness_fixtures()["bidi"].decode("utf-8")
        self.assertLess(body.index("Hello"), body.index("مرحبا"))

    def test_ime_fixture_is_the_committed_string_only(self):
        body = correctness_fixtures()["ime_committed"].decode("utf-8")
        self.assertEqual(body, "地\n")
        self.assertNotIn("di", body)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_fixtures.CorrectnessFixtures -v`

Expected: ERROR containing `cannot import name 'correctness_fixtures'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/fixtures/generate.py`:

```python
def correctness_fixtures():
    return {
        "unicode": "cafe\u0301 \U0002000b\n".encode("utf-8"),
        "emoji": "family \U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466 tone \U0001f44d\U0001f3fb\n".encode("utf-8"),
        "bidi": "Hello مرحبا\n".encode("utf-8"),
        "ime_committed": "地\n".encode("utf-8"),
    }
```

The unicode string is `cafe` plus U+0301, which is the combining acute, then U+2000B. The test looks for `e\u0301` and `𠀋`. `cafe\u0301` contains `e\u0301`. U+2000B encodes as `𠀋`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_fixtures.CorrectnessFixtures -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/fixtures/generate.py perf/tests/test_fixtures.py
git commit -m "test: add unicode emoji bidi and IME correctness fixtures"
```

---

### Task 3: Feature profiles and recorded fallback

**Files:**
- Create: `perf/fixtures/profiles.py`
- Modify: `perf/tests/test_fixtures.py`

**Interfaces:**
- Consumes: nothing from Task 2
- Produces: `feature_profile(name: str) -> dict` and `with_fallback(profile: dict, disabled: list[str]) -> dict`. Names are `P0`, `P1`, `P2`, `P3`. `P3` includes `busy_panel`. A fallback copies the profile and adds `disabled_features`. It does not change `name`.

- [ ] **Step 1: Write the failing test**

```python
from perf.fixtures.profiles import feature_profile, with_fallback


class FeatureProfiles(unittest.TestCase):
    def test_p0_has_no_optional_features(self):
        profile = feature_profile("P0")
        self.assertEqual(profile["collaboration"], "off")
        self.assertEqual(profile["ai_panel"], "off")
        self.assertEqual(profile["proofing"], "off")

    def test_p3_names_a_busy_panel(self):
        profile = feature_profile("P3")
        self.assertEqual(profile["busy_panel"], "on")
        self.assertEqual(profile["proofing"], "on")

    def test_fallback_keeps_the_requested_name_and_lists_what_dropped(self):
        dropped = with_fallback(feature_profile("P2"), ["proofing"])
        self.assertEqual(dropped["name"], "P2")
        self.assertEqual(dropped["disabled_features"], ["proofing"])
        self.assertEqual(dropped["proofing"], "off")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            feature_profile("P9")
        self.assertIn("feature profile", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_fixtures.FeatureProfiles -v`

Expected: ERROR containing `No module named 'perf.fixtures.profiles'`

- [ ] **Step 3: Write the minimal implementation**

`perf/fixtures/profiles.py`:

```python
_BASE = {
    "P0": {"collaboration": "off", "ai_panel": "off", "proofing": "off", "style_display": "off", "busy_panel": "off"},
    "P1": {"collaboration": "off", "ai_panel": "off", "proofing": "off", "style_display": "on", "busy_panel": "off"},
    "P2": {"collaboration": "off", "ai_panel": "off", "proofing": "on", "style_display": "on", "busy_panel": "off"},
    "P3": {"collaboration": "off", "ai_panel": "off", "proofing": "on", "style_display": "on", "busy_panel": "on"},
}


def feature_profile(name):
    if name not in _BASE:
        raise ValueError("feature profile %r" % (name,))
    profile = dict(_BASE[name])
    profile["name"] = name
    profile["disabled_features"] = []
    return profile


def with_fallback(profile, disabled):
    updated = dict(profile)
    updated["disabled_features"] = list(disabled)
    for feature in disabled:
        if feature not in updated:
            raise ValueError("unknown feature %r" % (feature,))
        updated[feature] = "off"
    return updated
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_fixtures.FeatureProfiles -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/fixtures/profiles.py perf/tests/test_fixtures.py
git commit -m "feat: record feature profiles and large-file fallbacks"
```

---

### Task 4: Size ladder and hostile-path refusal

**Files:**
- Modify: `perf/fixtures/profiles.py`
- Modify: `perf/tests/test_fixtures.py`

**Interfaces:**
- Consumes: `build_workload`
- Produces: `size_ladder() -> list[dict]` with ids `short-paragraphs`, `long-paragraphs`, `one-paragraph`, `mixed-utf8`, `search-dense`. `assert_not_hostile(path: str) -> None` raises `ValueError` if the path contains `hostile` or `bombs`.

- [ ] **Step 1: Write the failing test**

```python
from perf.fixtures.profiles import assert_not_hostile, size_ladder


class Ladder(unittest.TestCase):
    def test_ladder_ids_are_unique_and_named(self):
        rows = size_ladder()
        ids = [row["workload_id"] for row in rows]
        self.assertEqual(ids, [
            "short-paragraphs",
            "long-paragraphs",
            "one-paragraph",
            "mixed-utf8",
            "search-dense",
        ])
        self.assertEqual(len(set(ids)), len(ids))

    def test_search_profile_declares_a_match_count(self):
        search = [row for row in size_ladder() if row["workload_id"] == "search-dense"][0]
        self.assertEqual(search["match_count"], 1000)
        self.assertGreater(search["paragraphs"], 1)

    def test_shapes_are_not_treated_as_one_workload(self):
        rows = {row["workload_id"]: row for row in size_ladder()}
        self.assertGreater(rows["long-paragraphs"]["paragraph_chars"], rows["short-paragraphs"]["paragraph_chars"])
        self.assertEqual(rows["one-paragraph"]["paragraphs"], 1)

    def test_hostile_corpus_is_not_a_performance_fixture(self):
        with self.assertRaises(ValueError) as caught:
            assert_not_hostile("logs/bombs/tool/plate/B1/input.docx")
        self.assertIn("hostile", str(caught.exception))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest perf.tests.test_fixtures.Ladder -v`

Expected: ERROR containing `cannot import name 'size_ladder'`

- [ ] **Step 3: Write the minimal implementation**

Add to `perf/fixtures/profiles.py`:

```python
def size_ladder():
    return [
        {"workload_id": "short-paragraphs", "paragraphs": 100, "paragraph_chars": 40, "unicode_class": "ascii", "match_count": 0, "seed": 1},
        {"workload_id": "long-paragraphs", "paragraphs": 20, "paragraph_chars": 4000, "unicode_class": "ascii", "match_count": 0, "seed": 1},
        {"workload_id": "one-paragraph", "paragraphs": 1, "paragraph_chars": 8000, "unicode_class": "ascii", "match_count": 0, "seed": 1},
        {"workload_id": "mixed-utf8", "paragraphs": 10, "paragraph_chars": 80, "unicode_class": "mixed", "match_count": 0, "seed": 1},
        {"workload_id": "search-dense", "paragraphs": 50, "paragraph_chars": 80, "unicode_class": "ascii", "match_count": 1000, "seed": 1},
    ]


def assert_not_hostile(path):
    lowered = path.replace("\\", "/").lower()
    if "bomb" in lowered or "hostile" in lowered:
        raise ValueError("hostile packages are not performance fixtures: %s" % (path,))
```

`build_workload` currently rejects `unicode_class != "ascii"`. Leave `mixed-utf8` as a declared profile. Do not pass it to `build_workload` in this task. A later generator change may accept it. The test only checks the declared fields.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest perf.tests.test_fixtures -v`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add perf/fixtures/profiles.py perf/tests/test_fixtures.py
git commit -m "feat: declare the document size ladder and reject hostile fixtures"
```

## Acceptance criteria

- `python3 -m unittest perf.tests.test_fixtures -v` passes.
- Two calls with the same short profile return the same SHA-256.
- The emoji fixture contains U+1F468 U+200D U+1F469 U+200D U+1F467 U+200D U+1F466.
- `with_fallback` keeps the profile name and lists the disabled feature.
- A path containing `bombs` is rejected.
- No editor is launched and no multi-gigabyte file is written.

## Coverage ids

C02 C06 C08 C13 C14 C15 C21 C22 I01 I02 I03 I04 I05 I06
