from datetime import date

import pytest

from poe2_mcp.knowledge import TOPICS, Knowledge, Stamp, choose, load, parse_stamp, patch_key, save


def _text(patch: str, refreshed: str, body: str = "# Body\n") -> str:
    return f"---\npatch: {patch}\nrefreshed: {refreshed}\n---\n{body}"


def _k(source: str, patch: str, refreshed: str) -> Knowledge:
    return Knowledge(
        topic="trials",
        text=_text(patch, refreshed),
        source=source,
        stamp=Stamp(patch=patch, refreshed=date.fromisoformat(refreshed)),
    )


# --- patch_key ---------------------------------------------------------------------------------------

def test_patch_key_orders_hotfixes_patches_and_majors():
    ordered = ["0.5.5", "0.5.5a", "0.5.5d", "0.5.6", "0.9.0", "0.10.0", "1.0"]
    assert sorted(ordered, key=patch_key) == ordered
    assert len({patch_key(p) for p in ordered}) == len(ordered)


def test_patch_key_ignores_trailing_zero_parts():
    assert patch_key("1.0") == patch_key("1.0.0")


def test_patch_key_rejects_non_versions():
    with pytest.raises(ValueError):
        patch_key("latest")


# --- parse_stamp -------------------------------------------------------------------------------------

def test_parse_stamp_reads_the_header():
    assert parse_stamp(_text("0.5.5d", "2026-10-04")) == Stamp(patch="0.5.5d", refreshed=date(2026, 10, 4))


@pytest.mark.parametrize(
    "text",
    [
        "# No header at all\n",
        "---\npatch: 0.5.5\nrefreshed: October 4th\n---\n",
        "---\nrefreshed: 2026-10-04\n---\n",
        "---\npatch: latest\nrefreshed: 2026-10-04\n---\n",
        "Intro line\n---\npatch: 0.5.5\nrefreshed: 2026-10-04\n---\n",
    ],
)
def test_parse_stamp_returns_none_when_missing_or_malformed(text):
    assert parse_stamp(text) is None


# --- choose ------------------------------------------------------------------------------------------

def test_choose_local_with_newer_patch():
    assert choose(_k("bundled", "0.5.5", "2026-10-04"), _k("local", "0.6.0", "2026-10-01")).source == "local"


def test_choose_local_on_same_patch_with_later_date():
    assert choose(_k("bundled", "0.5.5", "2026-10-04"), _k("local", "0.5.5", "2026-10-05")).source == "local"


def test_choose_bundled_on_exact_tie():
    assert choose(_k("bundled", "0.5.5", "2026-10-04"), _k("local", "0.5.5", "2026-10-04")).source == "bundled"


def test_choose_bundled_when_local_is_older_patch_even_if_dated_later():
    assert choose(_k("bundled", "0.6.0", "2026-10-04"), _k("local", "0.5.5", "2026-12-01")).source == "bundled"


def test_choose_bundled_when_no_local():
    assert choose(_k("bundled", "0.5.5", "2026-10-04"), None).source == "bundled"


# --- load / save -------------------------------------------------------------------------------------

def test_load_without_local_returns_bundled(tmp_path):
    k = load("trials", tmp_path)
    assert k.source == "bundled"
    assert k.text.startswith("---\n")


def test_load_prefers_a_newer_local_copy(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "trials.md").write_text(_text("99.0", "2026-10-04"), encoding="utf-8")
    k = load("trials", tmp_path)
    assert k.source == "local"
    assert k.stamp.patch == "99.0"


def test_load_ignores_a_local_copy_with_a_bad_stamp(tmp_path):
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "trials.md").write_text("# no stamp\n", encoding="utf-8")
    assert load("trials", tmp_path).source == "bundled"


def test_load_unknown_topic_lists_the_topics(tmp_path):
    with pytest.raises(ValueError, match="trials, farming, crafting"):
        load("bossing", tmp_path)


def test_save_round_trips_through_load_with_lf_newlines(tmp_path):
    text = _text("99.0", "2026-10-04", "# Trials\r\nline\r\n")
    saved = save("trials", text, tmp_path)
    assert saved.source == "local"
    assert load("trials", tmp_path) == saved
    assert b"\r" not in (tmp_path / "knowledge" / "trials.md").read_bytes()


def test_save_rejects_text_without_a_stamp(tmp_path):
    with pytest.raises(ValueError, match="header"):
        save("trials", "# Trials\n", tmp_path)
    assert not (tmp_path / "knowledge" / "trials.md").exists()


def test_save_rejects_a_copy_not_newer_than_bundled(tmp_path):
    bundled = load("trials", tmp_path)
    with pytest.raises(ValueError, match="not newer"):
        save("trials", bundled.text, tmp_path)
    assert not (tmp_path / "knowledge" / "trials.md").exists()


@pytest.mark.parametrize("topic", TOPICS)
def test_every_bundled_topic_has_a_valid_stamp(topic, tmp_path):
    k = load(topic, tmp_path)
    assert k.source == "bundled"
    assert parse_stamp(k.text) == k.stamp
