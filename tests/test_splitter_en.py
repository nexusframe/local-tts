"""<en>...</en> tags: each segment that the splitter gives has its own pair of tags."""

from local_tts.splitter import SentenceStream, split_sentences


def test_sentences_inside_an_english_span_get_their_own_tags():
    assert split_sentences("<en>Hello. How are you?</en> Dobrze.") == [
        "<en>Hello.</en>",
        "<en>How are you?</en>",
        "Dobrze.",
    ]


def test_english_sentence_after_a_polish_sentence_is_a_new_sentence():
    assert split_sentences("Gotowe. <en>Good night</en>, do jutra.") == ["Gotowe.", "<en>Good night</en>, do jutra."]


def feed_by_char(stream: SentenceStream, text: str) -> list[str]:
    segments = [s for char in text for s in stream.feed(char)]
    return segments + stream.flush()


def test_stream_cut_at_a_comma_inside_a_span_keeps_tags_in_both_parts():
    text = "<en>Good morning, here is your plan.</en> Miłego dnia."
    assert feed_by_char(SentenceStream(), text) == [
        "<en>Good morning,</en>",
        "<en>here is your plan.</en>",
        "Miłego dnia.",
    ]


def test_stream_sentences_inside_a_span_keep_tags():
    text = "Mówię: <en>Hello. How are you? Fine.</en> Koniec."
    assert feed_by_char(SentenceStream(early_first=False), text) == [
        "Mówię: <en>Hello.</en>",
        "<en>How are you?</en>",
        "<en>Fine.</en>",
        "Koniec.",
    ]


def test_every_segment_for_the_backend_has_paired_tags():
    # The engine path: stream pieces -> normalize each segment -> split again.
    from local_tts.normalizer import normalize

    text = ("Zrobiłem <en>commit</en>, a potem <en>pull request</en>. <en>Good morning, Kate. "
            "How are you?</en> Testy w <en>Python</en>ie przeszły: 3 z 3. Powiedz <en>bye, bye")
    for size in (1, 2, 3, 5, 8, 13, len(text)):
        stream = SentenceStream(first_words=2)
        pieces = [text[i : i + size] for i in range(0, len(text), size)]
        segments = [s for piece in pieces for s in stream.feed(piece)] + stream.flush()
        for sentence in (s for segment in segments for s in split_sentences(normalize(segment))):
            assert sentence.count("<en>") == sentence.count("</en>"), (size, sentence)
            assert sentence.rfind("<en>") <= sentence.rfind("</en>"), (size, sentence)


def test_early_first_segment_can_end_after_a_tagged_word():
    stream = SentenceStream(first_words=2)
    assert stream.feed("Zrobiłem <en>commit</en> i wysłałem ") == ["Zrobiłem <en>commit</en>"]


def test_early_first_segment_inside_a_span_keeps_tags():
    stream = SentenceStream(first_words=2)
    assert stream.feed("<en>Good morning dear friend ") == ["<en>Good morning</en>"]
