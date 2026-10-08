from local_tts.splitter import split_sentences


def test_two_sentences_are_split_at_the_period():
    assert split_sentences("Jasne, już sprawdzam. Pogoda jest dobra.") == [
        "Jasne, już sprawdzam.",
        "Pogoda jest dobra.",
    ]


def test_no_split_after_polish_abbreviations():
    text = "Dzwonił dr Nowak, m.in. w sprawie wizyty. Mieszka np. przy ul. Długiej."
    assert split_sentences(text) == [
        "Dzwonił dr Nowak, m.in. w sprawie wizyty.",
        "Mieszka np. przy ul. Długiej.",
    ]


def test_itd_at_the_end_of_a_sentence_is_a_boundary():
    assert split_sentences("Kupiłem jabłka, gruszki itd. Potem wróciłem.") == [
        "Kupiłem jabłka, gruszki itd.",
        "Potem wróciłem.",
    ]


def test_ellipsis_and_mixed_punctuation_end_a_sentence():
    assert split_sentences("Myślałem, że… Naprawdę?! Tak.") == [
        "Myślałem, że…",
        "Naprawdę?!",
        "Tak.",
    ]


def test_no_split_inside_numbers_and_times():
    assert split_sentences("Kurs to 3.5 zł o 14:30. Koniec.") == [
        "Kurs to 3.5 zł o 14:30.",
        "Koniec.",
    ]


def test_quoted_sentence_starts_a_new_sentence():
    assert split_sentences("Powiedział tak. „Wracam jutro.”") == [
        "Powiedział tak.",
        "„Wracam jutro.”",
    ]


def test_empty_and_whitespace_text_gives_no_sentences():
    assert split_sentences("  \n ") == []
