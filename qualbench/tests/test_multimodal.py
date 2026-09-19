"""Unit tests for the qualbench `multimodal` category.

These cover the parts that must be right *before* a run is trusted:
manifest validation, base64 transport, answer extraction out of reasoning
text, and the grading/variance logic. No network and no real media are
required.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

import pytest

MM_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "multimodal"


def _load(module_name: str):
    """Import a multimodal module by path (the fixtures dir is not a package)."""
    if str(MM_DIR) not in sys.path:
        sys.path.insert(0, str(MM_DIR))
    spec = importlib.util.spec_from_file_location(module_name, MM_DIR / f"{module_name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


mm = _load("mm_common")
vr = _load("variance_report")


PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AF+AaZ7AAAAAElFTkSuQmCC"
)


def make_item(**overrides) -> dict:
    item = {
        "id": "charts-01-economics",
        "domain": "charts",
        "question": "What is the value?",
        "answer_type": "exact",
        "answer": "42",
        "images": ["a.png"],
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------- manifests


def test_validate_item_accepts_a_wellformed_item() -> None:
    mm.validate_item(make_item(), "test")


@pytest.mark.parametrize(
    "overrides, expected_message",
    [
        ({"domain": "cats"}, "unknown domain"),
        ({"answer_type": "vibes"}, "unknown answer_type"),
        ({"images": [], "video": None}, "neither 'images' nor 'video'"),
        ({"answer_type": "regex", "answer": "([unclosed"}, "not a valid regex"),
    ],
)
def test_validate_item_rejects_bad_items(overrides: dict, expected_message: str) -> None:
    with pytest.raises(ValueError, match=expected_message):
        mm.validate_item(make_item(**overrides), "test")


def test_validate_item_rejects_multiple_choice_without_options() -> None:
    with pytest.raises(ValueError, match="needs an 'options' list"):
        mm.validate_item(make_item(answer_type="multiple_choice", answer="A"), "test")


def test_validate_item_rejects_answer_outside_option_range() -> None:
    item = make_item(answer_type="multiple_choice", options=["x", "y"], answer="C")
    with pytest.raises(ValueError, match="must be a letter in"):
        mm.validate_item(item, "test")


def test_load_manifest_rejects_duplicate_ids(tmp_path, monkeypatch) -> None:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    line = json.dumps(make_item())
    (manifest_dir / "dupes.jsonl").write_text(f"{line}\n{line}\n", encoding="utf-8")
    monkeypatch.setattr(mm, "MANIFEST_DIR", manifest_dir)

    with pytest.raises(ValueError, match="duplicate item id"):
        mm.load_manifest("dupes")


def test_load_manifest_skips_comments_and_blank_lines(tmp_path, monkeypatch) -> None:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "ok.jsonl").write_text(
        "# a comment\n\n" + json.dumps(make_item()) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(mm, "MANIFEST_DIR", manifest_dir)

    items = mm.load_manifest("ok")
    assert [i["id"] for i in items] == ["charts-01-economics"]


def test_shipped_manifests_are_valid() -> None:
    """The committed manifests must load; a broken one would fail a whole run."""
    suites = mm.available_suites()
    assert "smoke" in suites, f"expected a smoke suite, found {suites}"
    for suite in suites:
        items = mm.load_manifest(suite)
        assert items, f"suite {suite} is empty"


def test_shipped_manifest_domains_have_thresholds() -> None:
    """Every domain used by a manifest needs a calibrated pass threshold."""
    check = _load("check")
    thresholds = check.load_thresholds()
    for suite in mm.available_suites():
        for item in mm.load_manifest(suite):
            assert item["domain"] in thresholds, (
                f"{suite}: domain {item['domain']!r} has no threshold"
            )


# ------------------------------------------------------- media + data URLs


def test_resolve_media_reports_every_missing_path(tmp_path) -> None:
    item = make_item(images=["there.png", "missing.png"])
    (tmp_path / "there.png").write_bytes(PNG_1x1)

    with pytest.raises(mm.MediaMissingError) as excinfo:
        mm.resolve_media(item, tmp_path)
    assert "missing.png" in str(excinfo.value)
    assert "there.png" not in str(excinfo.value)


def test_resolve_media_returns_absolute_paths(tmp_path) -> None:
    (tmp_path / "a.png").write_bytes(PNG_1x1)
    paths = mm.resolve_media(make_item(), tmp_path)
    assert paths == [tmp_path / "a.png"]


def test_encode_data_url_roundtrips(tmp_path) -> None:
    path = tmp_path / "x.png"
    path.write_bytes(PNG_1x1)

    url = mm.encode_data_url(path)
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == PNG_1x1
    assert mm.data_url_bytes(url) == len(PNG_1x1)


def test_guess_image_mime_uses_extension() -> None:
    assert mm.guess_image_mime(Path("a.jpg")) == "image/jpeg"
    assert mm.guess_image_mime(Path("a.JPEG")) == "image/jpeg"
    with pytest.raises(ValueError, match="cannot determine an image MIME type"):
        mm.guess_image_mime(Path("a.txt"))


def test_media_root_precedence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(mm.MEDIA_ROOT_ENV, str(tmp_path / "from-env"))
    assert mm.media_root() == (tmp_path / "from-env")
    assert mm.media_root(tmp_path / "explicit") == (tmp_path / "explicit")

    monkeypatch.delenv(mm.MEDIA_ROOT_ENV)
    assert mm.media_root() == mm.DEFAULT_MEDIA_ROOT


def test_build_messages_inlines_images_as_data_urls(tmp_path) -> None:
    (tmp_path / "a.png").write_bytes(PNG_1x1)
    item = make_item(answer_type="multiple_choice", options=["one", "two"], answer="B")

    messages = mm.build_messages(item, mm.resolve_media(item, tmp_path))

    assert messages[0]["role"] == "system"
    parts = messages[1]["content"]
    image_parts = [p for p in parts if p["type"] == "image_url"]
    assert len(image_parts) == 1
    # base64, never file:// -- the client may not share a filesystem with the server
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    text = [p for p in parts if p["type"] == "text"][0]["text"]
    assert "A. one" in text and "B. two" in text


# -------------------------------------------------------- video (stubbed)


def test_frame_timestamps_samples_midpoints() -> None:
    assert mm.frame_timestamps(10.0, 2) == [2.5, 7.5]
    assert mm.frame_timestamps(4.0, 4) == [0.5, 1.5, 2.5, 3.5]
    assert len(mm.frame_timestamps(0.0, 3)) == 3


def test_frame_timestamps_rejects_zero_frames() -> None:
    with pytest.raises(ValueError):
        mm.frame_timestamps(10.0, 0)


def test_extract_video_frames_reports_missing_media_first(tmp_path) -> None:
    """A missing file must be a media error, not 'ffmpeg not installed'."""
    with pytest.raises(mm.MediaMissingError):
        mm.extract_video_frames(tmp_path / "nope.mp4", 4)


def test_extract_video_frames_without_ffmpeg_is_a_clear_error(tmp_path, monkeypatch) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not really a video")
    monkeypatch.setattr(mm, "ffmpeg_available", lambda: False)

    with pytest.raises(mm.VideoSupportUnavailableError, match="ffmpeg"):
        mm.extract_video_frames(video, 4)


# ----------------------------------------------------- answer extraction


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Let me think...\n\nAnswer: 42", "42"),
        ("blah\n**Answer:** 42", "42"),
        ("reasoning\nFinal Answer: 42", "42"),
        ("so the value is \\boxed{42}", "42"),
        ("Answer: 17\nActually wait.\nAnswer: 42", "42"),
        ("Answer: 42.", "42"),
        ("Answer: `42`", "42"),
        ("no marker at all\n42", "42"),
        ("", ""),
    ],
)
def test_extract_answer_handles_reasoning_formats(text: str, expected: str) -> None:
    assert mm.extract_answer(text, "exact") == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Answer: B", "B"),
        ("thinking...\nB", "B"),
        ("thinking...\n(B)", "B"),
        ("The correct option is C.", "C"),
    ],
)
def test_extract_answer_multiple_choice(text: str, expected: str) -> None:
    assert mm.extract_answer(text, "multiple_choice", n_options=4) == expected


def test_out_of_range_letter_is_never_graded_correct() -> None:
    """A letter beyond the option list must not score, whatever we extract.

    Extraction deliberately still surfaces the raw trailing text (it is
    what the model actually said, which is what you want when debugging a
    failure); the invariant that matters is that it cannot be credited.
    """
    item = make_item(answer_type="multiple_choice", options=["cat", "dog"], answer="B")
    for response in ("hmm\nD", "Answer: D", "Answer: Z"):
        assert not mm.grade_item(item, response)["correct"]


# ------------------------------------------------------------- normalizing


@pytest.mark.parametrize(
    "a, b",
    [
        ("The Answer", "answer"),
        ("Hello, World!", "hello world"),
        ("$1,000", "1,000"),
        ("\\text{mass}", "mass"),
    ],
)
def test_normalize_text_collapses_formatting(a: str, b: str) -> None:
    assert mm.normalize_text(a) == mm.normalize_text(b)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("42", 42.0),
        ("1,234", 1234.0),
        ("-3.5", -3.5),
        ("about 7 units", 7.0),
        ("no digits", None),
    ],
)
def test_parse_number(raw: str, expected: float | None) -> None:
    assert mm.parse_number(raw) == expected


# ---------------------------------------------------------------- grading


def test_grade_exact_match_is_reported_as_exact() -> None:
    result = mm.grade_item(make_item(), "Answer: 42")
    assert result["correct"] and result["match_mode"] == "exact"


def test_grade_normalized_match_is_flagged_as_such() -> None:
    """Formatting-only credit must be distinguishable from a clean hit."""
    item = make_item(answer="New York City")
    result = mm.grade_item(item, "Answer: the new york city")
    assert result["correct"] and result["match_mode"] == "normalized"


def test_grade_numeric_tolerance() -> None:
    item = make_item(answer_type="numeric", answer="100", rel_tol=0.05)
    within = mm.grade_item(item, "Answer: 103")
    outside = mm.grade_item(item, "Answer: 130")
    assert within["correct"] and within["match_mode"] == "numeric"
    assert not outside["correct"]


def test_grade_numeric_exact_zero_tolerance() -> None:
    item = make_item(answer_type="numeric", answer="5", rel_tol=0.0, abs_tol=0.0)
    assert mm.grade_item(item, "Answer: 5")["correct"]
    assert not mm.grade_item(item, "Answer: 6")["correct"]


def test_grade_multiple_choice_letter_and_option_text() -> None:
    item = make_item(answer_type="multiple_choice", options=["cat", "dog"], answer="B")
    by_letter = mm.grade_item(item, "Answer: B")
    by_text = mm.grade_item(item, "Answer: dog")
    wrong = mm.grade_item(item, "Answer: A")

    assert by_letter["correct"] and by_letter["match_mode"] == "exact"
    # writing out the right option without the letter is still correct
    assert by_text["correct"] and by_text["match_mode"] == "normalized"
    assert not wrong["correct"]


def test_grade_answer_any_of_accepts_alternatives() -> None:
    item = make_item(answer="H2O", answer_any_of=["water"])
    assert mm.grade_item(item, "Answer: water")["correct"]


def test_grade_contains_and_regex_types() -> None:
    contains = make_item(answer_type="contains", answer="mitochondria")
    regex = make_item(answer_type="regex", answer=r"\b\d{3}-\d{4}\b")

    assert mm.grade_item(contains, "It is the Mitochondria, clearly.")["correct"]
    assert not mm.grade_item(contains, "It is the nucleus.")["correct"]
    assert mm.grade_item(regex, "Answer: 555-1234")["correct"]
    assert not mm.grade_item(regex, "Answer: nope")["correct"]


def test_grade_empty_response_is_not_silently_correct() -> None:
    result = mm.grade_item(make_item(), "")
    assert not result["correct"]
    assert "could not extract" in result["reasons"][0]


# ------------------------------------------------------ summarize/variance


def graded(item_id: str, domain: str, correct: bool, mode: str = "exact") -> dict:
    return {
        "id": item_id,
        "domain": domain,
        "correct": correct,
        "match_mode": mode if correct else "none",
        "expected": "x",
        "extracted": "x" if correct else "y",
        "reasons": [],
    }


def test_summarize_reports_per_domain_and_format_slack() -> None:
    results = [
        graded("a", "charts", True, "exact"),
        graded("b", "charts", True, "normalized"),
        graded("c", "photos", False),
        graded("d", "photos", True, "exact"),
    ]
    s = mm.summarize(results)

    assert s["n_total"] == 4 and s["n_correct"] == 3
    assert s["accuracy"] == 0.75
    assert s["strict_accuracy"] == 0.5
    assert s["format_slack"] == 0.25
    assert s["domains"]["charts"]["accuracy"] == 1.0
    assert s["domains"]["photos"]["accuracy"] == 0.5


def test_domain_variance_identifies_best_and_worst() -> None:
    s = mm.summarize(
        [
            graded("a", "charts", False),
            graded("b", "charts", False),
            graded("c", "photos", True),
            graded("d", "photos", True),
        ]
    )
    v = mm.domain_variance(s)
    assert v["worst_domain"] == "charts"
    assert v["best_domain"] == "photos"
    assert v["range"] == 1.0


def test_summarize_handles_empty_input() -> None:
    s = mm.summarize([])
    assert s["n_total"] == 0 and s["accuracy"] == 0.0
    assert mm.domain_variance(s)["n_domains"] == 0


# --------------------------------------------------------- variance report


def test_error_breakdown_separates_plumbing_from_wrong_answers() -> None:
    records = [
        graded("a", "charts", True),
        graded("b", "charts", False),
        {**graded("c", "photos", False), "error_kind": "truncated"},
        {**graded("d", "photos", False), "error_kind": "setup"},
        {**graded("e", "photos", False), "extracted": ""},
    ]
    e = vr.error_breakdown(records)

    assert e["wrong_answers"] == 1
    assert e["unextractable"] == 1
    assert e["by_kind"] == {"truncated": 1, "setup": 1}
    # the two plumbing failures must not drag down the model's own accuracy
    assert e["n_answered"] == 3
    assert e["accuracy_over_answered"] == pytest.approx(1 / 3)


def test_stability_finds_items_that_flip_between_runs() -> None:
    records = [
        {**graded("a", "charts", True), "_run": "r1"},
        {**graded("a", "charts", False), "_run": "r2"},
        {**graded("b", "charts", True), "_run": "r1"},
        {**graded("b", "charts", True), "_run": "r2"},
    ]
    st = vr.stability(records)

    assert st["n_runs"] == 2
    assert st["stable_correct"] == 1
    assert [f["id"] for f in st["flaky_items"]] == ["a"]
    assert st["accuracy_spread"] == 0.5


def test_stability_with_a_single_run_reports_nothing_repeated() -> None:
    st = vr.stability([{**graded("a", "charts", True), "_run": "r1"}])
    assert st["n_items_repeated"] == 0
    assert st["flaky_items"] == []


def test_latest_run_only_deduplicates_per_item() -> None:
    records = [
        {**graded("a", "charts", True), "_run": "r1"},
        {**graded("a", "charts", False), "_run": "r2"},
    ]
    unique = vr.latest_run_only(records)
    assert len(unique) == 1 and unique[0]["_run"] == "r2"


def test_chance_baseline_from_option_counts() -> None:
    manifest = {
        "a": {"answer_type": "multiple_choice", "options": ["1", "2"]},
        "b": {"answer_type": "multiple_choice", "options": ["1", "2", "3", "4"]},
        "c": {"answer_type": "exact"},
    }
    records = [graded("a", "charts", True), graded("b", "charts", True), graded("c", "charts", True)]
    # mean of 1/2 and 1/4; the free-form item has no chance rate
    assert vr.chance_baseline(records, manifest) == pytest.approx(0.375)


def test_chance_baseline_is_none_without_multiple_choice() -> None:
    manifest = {"a": {"answer_type": "exact"}}
    assert vr.chance_baseline([graded("a", "charts", True)], manifest) is None


def test_group_accuracy_buckets_unknown_fields() -> None:
    groups = vr.group_accuracy([graded("a", "charts", True)], "subject")
    assert groups["(unknown)"]["n_total"] == 1


def test_load_records_reads_meta_and_items(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text(
        json.dumps({"_meta": True, "suite": "smoke", "model": "m"}) + "\n"
        + json.dumps(graded("a", "charts", True)) + "\n",
        encoding="utf-8",
    )
    records, runs = vr.load_records([path])

    assert runs[0]["suite"] == "smoke" and runs[0]["n_items"] == 1
    assert records[0]["_run"] == str(path)


def test_load_records_rejects_a_file_with_no_items(tmp_path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text(json.dumps({"_meta": True, "suite": "smoke"}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no item records"):
        vr.load_records([path])


def test_grade_multiple_choice_accepts_ambiguous_alternatives() -> None:
    """An item with a genuine tie must credit every defensible option.

    Grading a model wrong for picking an equally-correct option measures the
    fixture, not the model.
    """
    item = make_item(
        answer_type="multiple_choice",
        options=["a", "b", "c"],
        answer="B",
        answer_any_of=["C"],
    )
    assert mm.grade_item(item, "Answer: B")["correct"]
    assert mm.grade_item(item, "Answer: C")["correct"]
    assert not mm.grade_item(item, "Answer: A")["correct"]


def test_validate_item_rejects_out_of_range_answer_any_of() -> None:
    item = make_item(answer_type="multiple_choice", options=["a", "b"], answer="A",
                     answer_any_of=["D"])
    with pytest.raises(ValueError, match="answer_any_of entry"):
        mm.validate_item(item, "test")


# ------------------------------------------------------------- thresholds


def test_load_thresholds_reads_shipped_file() -> None:
    check = _load("check")
    thresholds = check.load_thresholds()
    for domain in mm.KNOWN_DOMAINS:
        assert 0.0 <= thresholds[domain] <= 1.0


def test_load_thresholds_ignores_doc_keys(tmp_path, monkeypatch) -> None:
    """The shipped file carries a _README list; it must not be parsed as a number."""
    check = _load("check")
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps({"_README": ["notes", "more notes"], "charts": 0.3}))
    monkeypatch.setattr(check, "THRESHOLDS_FILE", path)

    thresholds = check.load_thresholds()
    assert thresholds["charts"] == 0.3
    assert "_README" not in thresholds


@pytest.mark.parametrize(
    "payload, expected_message",
    [
        ({"not-a-domain": 0.5}, "not a known visual domain"),
        ({"charts": "high"}, "must be a number"),
        ({"charts": 1.5}, r"must be in \[0, 1\]"),
    ],
)
def test_load_thresholds_rejects_bad_overrides(
    tmp_path, monkeypatch, payload: dict, expected_message: str
) -> None:
    check = _load("check")
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(check, "THRESHOLDS_FILE", path)

    with pytest.raises(ValueError, match=expected_message):
        check.load_thresholds()


# ------------------------------------------- multiple-choice commitment


@pytest.mark.parametrize(
    "extracted, expected_letter",
    [
        ("B", "B"),
        ("(B)", "B"),
        ("B.", "B"),
        ("b", "B"),
        ("The answer is B", "B"),
        ("B (dog)", "B"),
        ("Cannot determine", None),
    ],
)
def test_resolve_choice_letter_unambiguous(extracted: str, expected_letter: str | None) -> None:
    letter, ambiguous = mm.resolve_choice_letter(extracted, 3)
    assert not ambiguous
    assert letter == expected_letter


@pytest.mark.parametrize("extracted", ["Both B and C", "B or C", "either A or B"])
def test_resolve_choice_letter_detects_hedging(extracted: str) -> None:
    letter, ambiguous = mm.resolve_choice_letter(extracted, 3)
    assert ambiguous and letter is None


def test_resolve_choice_letter_ignores_out_of_range_letters() -> None:
    # 'C' is not an option when there are only two, so "B or C" is not a hedge
    letter, ambiguous = mm.resolve_choice_letter("B or C", 2)
    assert letter == "B" and not ambiguous


def test_hedged_multiple_choice_answer_gets_no_credit() -> None:
    """A reply that declines to choose must not be credited.

    Grading only the first character would score "Both B and C" as a
    correct 'B', silently inflating multiple-choice accuracy.
    """
    item = make_item(answer_type="multiple_choice", options=["cat", "dog", "bird"], answer="B")
    for hedge in ("Answer: Both B and C", "Answer: B or C"):
        result = mm.grade_item(item, hedge)
        assert not result["correct"]
        assert "does not commit to a single option" in result["reasons"][0]


def test_negated_option_gets_no_credit() -> None:
    item = make_item(answer_type="multiple_choice", options=["cat", "dog", "bird"], answer="B")
    assert not mm.grade_item(item, "Answer: Definitely not B, it is A")["correct"]


def test_multiple_choice_letter_inside_a_sentence_still_counts() -> None:
    item = make_item(answer_type="multiple_choice", options=["cat", "dog", "bird"], answer="B")
    assert mm.grade_item(item, "Answer: The answer is B")["correct"]
    assert mm.grade_item(item, "Answer: B (dog)")["correct"]


def test_stability_excludes_plumbing_failures_from_flakiness() -> None:
    """A truncated run must not be counted as the model changing its answer.

    A truncated generation yields an empty answer, which looks exactly like
    a wrong-answer flip if you only compare booleans -- that would blame the
    model for the harness's token budget.
    """
    records = [
        {**graded("a", "diagrams", False), "_run": "r1", "error_kind": "truncated"},
        {**graded("a", "diagrams", True), "_run": "r2"},
        {**graded("b", "diagrams", True), "_run": "r1"},
        {**graded("b", "diagrams", False), "_run": "r2"},
    ]
    st = vr.stability(records)

    assert [f["id"] for f in st["flaky_items"]] == ["b"]
    assert [i["id"] for i in st["unmeasurable_items"]] == ["a"]
    # flake rate is over observable items only, so 1 of 2, not 1 of 2-with-noise
    assert st["n_measurable"] == 1
    assert st["flake_rate"] == 1.0


def test_stability_flake_rate_zero_when_all_attempts_plumbing() -> None:
    records = [
        {**graded("a", "diagrams", False), "_run": "r1", "error_kind": "truncated"},
        {**graded("a", "diagrams", False), "_run": "r2", "error_kind": "truncated"},
    ]
    st = vr.stability(records)
    assert st["flaky_items"] == []
    assert st["n_measurable"] == 0
    assert st["flake_rate"] == 0.0


# -------------------------------------------------------- run config guard


def test_compare_run_configs_flags_differing_settings() -> None:
    """Runs at different token budgets must not be reported as noise.

    Aggregating them and calling the gap 'run-to-run variance' would blame
    the model for a configuration change.
    """
    runs = [
        {"path": "r1.jsonl", "config": {"max_tokens": 2048}},
        {"path": "r2.jsonl", "config": {"max_tokens": 16384}},
    ]
    cmp = vr.compare_run_configs(runs)

    assert not cmp["comparable"]
    assert [d["setting"] for d in cmp["differing"]] == ["max_tokens"]
    assert cmp["differing"][0]["values"][0] == {"run": "r1.jsonl", "value": 2048}


def test_compare_run_configs_accepts_identical_settings() -> None:
    runs = [
        {"path": "r1.jsonl", "config": {"max_tokens": 4096}},
        {"path": "r2.jsonl", "config": {"max_tokens": 4096}},
    ]
    cmp = vr.compare_run_configs(runs)
    assert cmp["comparable"] and cmp["differing"] == []


def test_compare_run_configs_flags_missing_metadata() -> None:
    """Older records without config metadata must not be silently trusted."""
    runs = [{"path": "r1.jsonl"}, {"path": "r2.jsonl", "config": {"max_tokens": 1}}]
    cmp = vr.compare_run_configs(runs)

    assert not cmp["comparable"]
    assert cmp["runs_without_config"] == ["r1.jsonl"]


def test_load_records_picks_up_config_metadata(tmp_path) -> None:
    path = tmp_path / "run.jsonl"
    path.write_text(
        json.dumps({"_meta": True, "suite": "smoke", "config": {"max_tokens": 16384}})
        + "\n" + json.dumps(graded("a", "charts", True)) + "\n",
        encoding="utf-8",
    )
    _, runs = vr.load_records([path])
    assert runs[0]["config"] == {"max_tokens": 16384}


# ------------------------------------------------- incremental record writing


def test_records_are_flushed_incrementally(tmp_path) -> None:
    """A crash mid-run must not lose already-completed items.

    A full MMMU run takes 1-2 hours; buffering every record until the end
    would throw away all GPU time on a crash or timeout.
    """
    check = _load("check")
    path, write_record, close = check.make_records_writer(
        "smoke", "m", "http://x", tmp_path / "r.jsonl", config={"max_tokens": 16384}
    )
    write_record(graded("a", "charts", True))
    # readable *before* close -- that is the whole point
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    header = json.loads(lines[0])
    assert header["config"] == {"max_tokens": 16384}

    write_record(graded("b", "charts", False))
    close()
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_make_records_writer_honours_explicit_path(tmp_path) -> None:
    check = _load("check")
    out = tmp_path / "nested" / "run.jsonl"
    path, _write, close = check.make_records_writer("smoke", "m", "http://x", out)
    close()
    assert path == out and out.is_file()


def test_check_suite_consistency_detects_mixed_suites() -> None:
    """Mixing suites into one headline is a weighted average of two
    different measurements, not one result."""
    mixed = vr.check_suite_consistency(
        [{"suite": "mmmu-subset"}, {"suite": "smoke"}]
    )
    assert not mixed["consistent"]
    assert mixed["mixed"] == ["mmmu-subset", "smoke"]

    same = vr.check_suite_consistency(
        [{"suite": "mmmu-subset"}, {"suite": "mmmu-subset"}]
    )
    assert same["consistent"] and same["mixed"] == []


def test_check_suite_consistency_handles_missing_suite() -> None:
    result = vr.check_suite_consistency([{"path": "x"}])
    assert result["suites"] == ["(unknown)"]


# ------------------------------------------------------ dashboard labelling


def test_dashboard_states_which_run_supplies_the_tables() -> None:
    """Multi-run dashboards must not imply their tables are an average.

    The per-item tables come from the latest run only; older runs feed the
    stability section. Labelling that as "runs aggregated" would suggest a
    blended accuracy that does not describe any actual run.
    """
    dash = _load("dashboard")
    records = [
        {**graded("a", "charts", True), "_run": "run1.jsonl"},
        {**graded("a", "charts", False), "_run": "run2.jsonl"},
    ]
    runs = [
        {"path": "run1.jsonl", "suite": "smoke", "n_items": 1},
        {"path": "run2.jsonl", "suite": "smoke", "n_items": 1},
    ]
    report = vr.build_report(records, runs, "smoke")
    md = dash.render_markdown(report, {}, {"benchmarks": {}})

    assert "Runs supplied: 2" in md
    assert "Runs aggregated" not in md
    assert "`run2.jsonl` (1 items) (headline/tables below)" in md
    assert "last run only" in md
