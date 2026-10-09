"""The phonemes are real espeak-ng output of piper-tts 1.8.0 for the given text."""

from local_tts.backends.phonemes import lengthen_trz


def p(text: str) -> list[str]:
    return list(text)


def test_trz_gets_a_long_sz():
    assert lengthen_trz("trzy", [p("tʃˈɨ")]) == [p("tʃʃˈɨ")]


def test_cz_does_not_change():
    assert lengthen_trz("czy", [p("tʃɨ")]) == [p("tʃɨ")]


def test_only_trz_changes_in_a_sentence_with_trz_and_cz():
    text = "Trzy razy sprawdzał, czy okno jest zamknięte."
    phonemes = [p("tʃˈɨ rˈazɨ sprˈavdʑaw, tʃɨ ˈɔknɔ jɛzd zamkɲʲˈɛntɛ.")]
    assert lengthen_trz(text, phonemes) == [p("tʃʃˈɨ rˈazɨ sprˈavdʑaw, tʃɨ ˈɔknɔ jɛzd zamkɲʲˈɛntɛ.")]


def test_words_that_espeak_joins_do_not_break_the_order():
    # espeak joins "na to" into one word; the order of tʃ is still the order of trz/cz.
    text = "Trzeba przyznać, że Piotr patrzył na to trzeźwo."
    phonemes = [p("tʃˈɛba pʃˈɨznatɕ, ʒˈɛ pʲˈɔtr pˈatʃɨw nˈatɔ tʃˈɛʑvɔ.")]
    assert lengthen_trz(text, phonemes) == [p("tʃʃˈɛba pʃˈɨznatɕ, ʒˈɛ pʲˈɔtr pˈatʃʃɨw nˈatɔ tʃʃˈɛʑvɔ.")]


def test_order_continues_across_espeak_sentences():
    assert lengthen_trz("Czy? Trzy.", [p("tʃˈɨ?"), p("tʃˈɨ.")]) == [p("tʃˈɨ?"), p("tʃʃˈɨ.")]


def test_no_change_when_the_counts_do_not_agree():
    # Unknown spelling of tʃ (count 2 in phonemes, 1 in text): keep espeak output.
    phonemes = [p("tʃˈɨ tʃˈɨ")]
    assert lengthen_trz("trzy dżdżu", phonemes) == phonemes
