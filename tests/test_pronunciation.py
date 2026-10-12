import os

import pytest

from local_tts.pronunciation import PronunciationDictionary, apply_aliases


def test_whole_word_is_replaced():
    aliases = {"nginx": "engine x"}
    assert apply_aliases("Restart nginx now.", aliases) == "Restart engine x now."
    assert apply_aliases("Restart nginxd now.", aliases) == "Restart nginxd now."


def test_case_is_significant():
    assert apply_aliases("PIT i pit.", {"PIT": "pit"}) == "pit i pit."


def test_longer_entry_wins():
    aliases = {"GitHub": "<en>github</en>", "GitHub Actions": "<en>github actions</en>"}
    assert apply_aliases("GitHub Actions i GitHub.", aliases) == "<en>github actions</en> i <en>github</en>."


def test_text_in_english_tags_does_not_change():
    aliases = {"GitHub": "<en>github</en>", "en": "EN"}
    assert apply_aliases("Na <en>GitHub</en> i GitHub.", aliases) == "Na <en>GitHub</en> i <en>github</en>."


def write(path, content, mtime):
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_missing_file_gives_no_aliases(tmp_path):
    assert PronunciationDictionary(tmp_path / "none.toml").aliases("pl") == {}


def test_file_has_one_section_for_each_language(tmp_path):
    path = tmp_path / "pronunciation.toml"
    write(path, '[pl]\n"PIT" = "pit"\n\n[en]\n"nginx" = "engine x"\n', 1000)
    dictionary = PronunciationDictionary(path)
    assert dictionary.aliases("pl") == {"PIT": "pit"}
    assert dictionary.aliases("en") == {"nginx": "engine x"}


def test_changed_file_is_read_again(tmp_path):
    path = tmp_path / "pronunciation.toml"
    write(path, '[pl]\n"PIT" = "pit"\n', 1000)
    dictionary = PronunciationDictionary(path)
    dictionary.aliases("pl")

    write(path, '[pl]\n"PIT" = "pe i te"\n', 2000)

    assert dictionary.aliases("pl") == {"PIT": "pe i te"}


@pytest.mark.parametrize("bad", ['[pl\n"PIT" = "pit"\n', '[pl]\n"PIT" = 5\n', 'pl = "x"\n', '[pl]\n" " = "x"\n'])
def test_invalid_file_keeps_the_last_valid_aliases(tmp_path, caplog, bad):
    path = tmp_path / "pronunciation.toml"
    write(path, '[pl]\n"PIT" = "pit"\n', 1000)
    dictionary = PronunciationDictionary(path)
    dictionary.aliases("pl")

    write(path, bad, 2000)

    assert dictionary.aliases("pl") == {"PIT": "pit"}
    assert "pronunciation" in caplog.text
