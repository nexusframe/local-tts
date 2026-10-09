from local_tts.splitter import SentenceStream, split_sentences


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


def test_no_split_after_abbreviations_that_the_normalizer_expands():
    text = "Mam ok. 5 km do domu. Podaj tel. 600 100 200, tj. Nowak. Dzwonił inż. Kowalski."
    assert split_sentences(text) == [
        "Mam ok. 5 km do domu.",
        "Podaj tel. 600 100 200, tj. Nowak.",
        "Dzwonił inż. Kowalski.",
    ]


def test_ok_before_a_word_ends_the_sentence():
    assert split_sentences("Jest ok. Wracam.") == ["Jest ok.", "Wracam."]


def feed_all(stream: SentenceStream, pieces: list[str]) -> list[list[str]]:
    """Feed the pieces one by one. Return the segments that each feed gave, then the flush."""
    return [stream.feed(piece) for piece in pieces] + [stream.flush()]


def test_stream_gives_a_sentence_when_the_next_one_starts():
    stream = SentenceStream(early_first=False)
    assert feed_all(stream, ["Jasne, już", " sprawdzam.", " Pogoda", " jest dobra."]) == [
        [],
        [],
        ["Jasne, już sprawdzam."],
        [],
        ["Pogoda jest dobra."],
    ]


def test_first_segment_ends_at_the_first_comma():
    stream = SentenceStream()
    assert feed_all(stream, ["Jasne,", " już", " sprawdzam.", " Tak,", " pogoda", " jest", " dobra."]) == [
        [],
        ["Jasne,"],
        [],
        ["już sprawdzam."],
        [],
        [],
        [],
        ["Tak, pogoda jest dobra."],
    ]


def test_first_segment_without_comma_ends_after_the_word_limit():
    stream = SentenceStream(first_words=4)
    pieces = ["Dzisiaj", " rano", " poszedłem", " do", " sklepu", " po", " chleb."]
    assert feed_all(stream, pieces) == [[], [], [], [], [], ["Dzisiaj rano poszedłem do"], [], ["sklepu po chleb."]]


def test_word_limit_cut_is_never_next_to_a_number_or_abbreviation():
    stream = SentenceStream(first_words=2)
    pieces = ["Idę", " do", " 5", " km", " ul.", " Długą", " i", " wracam."]
    assert feed_all(stream, pieces) == [[], [], [], [], [], [], [], ["Idę do 5 km ul. Długą"], ["i wracam."]]
