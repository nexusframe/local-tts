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


def test_dz_gets_d_and_z():
    # espeak-ng gives "dʑ" for "dz" (widzenia) and for "dzi"/"dź" (dzień). Listening test 2026-10-12.
    from local_tts.backends.phonemes import fix_dz

    assert fix_dz("Do widzenia.", [p("dɔ vidʑˈɛɲʲa.")]) == [p("dɔ vidzˈɛɲʲa.")]
    assert fix_dz("Dzwon", [p("dʑvˈɔn")]) == [p("dzvˈɔn")]


def test_dzi_and_dz_with_accent_do_not_change():
    from local_tts.backends.phonemes import fix_dz

    text = "Dzień dobry, chodźmy do urządzenia."
    phonemes = [p("dʑˈɛɲ dˈɔbrɨ, xˈɔdʑmɨ dɔ ˌuʒɔndʑˈɛɲʲa.")]
    assert fix_dz(text, phonemes) == [p("dʑˈɛɲ dˈɔbrɨ, xˈɔdʑmɨ dɔ ˌuʒɔndzˈɛɲʲa.")]
    assert fix_dz("dżem", [p("dʒˈɛm")]) == [p("dʒˈɛm")]


def test_dz_no_change_when_the_counts_do_not_agree():
    # "wódz" is "vuts", and "być dobrym" has a "dʑ" from "ć": keep espeak output.
    assert fix_dz_unchanged("Wódz widzi.", [p("vˈuts vˈidʑi.")])
    assert fix_dz_unchanged("Być do widzenia.", [p("bˈɨdʑ dɔ vidʑˈɛɲʲa.")])


def fix_dz_unchanged(text: str, phonemes: list[list[str]]) -> bool:
    from local_tts.backends.phonemes import fix_dz

    return fix_dz(text, phonemes) == phonemes
