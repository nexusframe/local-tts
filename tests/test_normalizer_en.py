"""<en>...</en> tags: the normalizer keeps English text out of the Polish rules."""

from local_tts.normalizer import normalize


def test_english_span_is_kept_and_polish_text_is_normalized():
    assert normalize("Zrobiłem <en>commit</en> i 3 testy.") == "Zrobiłem <en>commit</en> i trzy testy."


def test_polish_rules_do_not_change_english_text():
    # Without protection: "piętnaście", "doktor", "kilometrów" and a removed [link].
    text = "Mam <en>iPhone 15</en>, <en>Dr. Who</en> i <en>5 km [link]</en>."
    assert normalize(text) == "Mam <en>iPhone 15</en>, <en>Dr. Who</en> i <en>5 km [link]</en>."


def test_polish_ending_after_the_tag_stays_attached():
    assert normalize("Testy w <en>Python</en>ie przeszły.") == "Testy w <en>Python</en>ie przeszły."


def test_whitespace_inside_a_span_is_collapsed():
    assert normalize("To <en>  pull\n request </en>.") == "To <en>pull request</en>."


def test_empty_span_is_removed():
    assert normalize("Dobrze <en> </en>zrobione.") == "Dobrze zrobione."


def test_tag_without_a_pair_is_removed():
    # An unclosed <en> ends the span at the end of the text (the LLM forgot </en>).
    assert normalize("To jest </en>błąd.") == "To jest błąd."
    assert normalize("Powiedz <en>good night") == "Powiedz <en>good night</en>"


def test_apostrophe_marks_an_english_word_with_a_polish_ending():
    # Polish spelling of English words: the apostrophe separates the Polish ending.
    assert normalize("Zrobiłem commit'a i wrzuciłem na GitHub'a.") == "Zrobiłem <en>commit</en>a i wrzuciłem na <en>GitHub</en>a."
    assert normalize("Muszę to push'ować.") == "Muszę to <en>push</en>ować."


def test_apostrophe_after_a_tag_is_removed():
    assert normalize("Zrobiłem <en>commit</en>'a.") == "Zrobiłem <en>commit</en>a."


def test_english_contractions_are_not_polish_endings():
    assert normalize("<en>It's fine, don't worry.</en>") == "<en>It's fine, don't worry.</en>"
    assert normalize("Napisał „don't”.") == "Napisał „don't”."
