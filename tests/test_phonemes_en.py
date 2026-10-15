"""<en>...</en> tags: English phonemes for the Polish Piper voices.

The English IPA is real espeak-ng en-us output of piper-tts 1.8.0. The expected
Polish phonemes are the "ipa_pl" variant that won the listening test (2026-10-10).
"""

from local_tts.backends.phonemes import to_polish_phonemes


def test_english_only_phonemes_change_to_the_nearest_polish_phonemes():
    assert to_polish_phonemes("ɡˈʊd mˈɔːɹnɪŋ!") == "ɡˈud mˈɔrnɨŋ!"
    assert to_polish_phonemes("hˈɪɹ ɪz jʊɹ plˈæn fɔːɹ tədˈeɪ.") == "xˈɨr ɨz jur plˈɛn fɔr tɛdˈɛj."
    assert to_polish_phonemes("wʊd juː lˈaɪk mˌiː tə ɹˈiːd ðə nˈuːz?") == "wud ju lˈajk mˌi tɛ rˈid dɛ nˈuz?"


# Fakes: "Polish phonemes" are the lowercase text, "English phonemes" the uppercase
# text. "|" marks where the phonemizer starts a new sentence.
def fake_polish(text: str) -> list[list[str]]:
    # Like espeak-ng, the fake drops punctuation before the first word.
    text = text.lstrip(".,!?;: ")
    return [list(s) for s in text.lower().split("|")] if text else []


def fake_english(text: str) -> list[list[str]]:
    return [list(s) for s in text.upper().split("|")]


def mixed(text: str) -> list[str]:
    from local_tts.backends.phonemes import phonemize_mixed

    return ["".join(s) for s in phonemize_mixed(text, fake_polish, fake_english)]


def test_text_without_tags_goes_to_the_polish_phonemizer_only():
    assert mixed("Trzy razy|Czy") == ["trzy razy", "czy"]


def test_english_span_inside_a_sentence_stays_in_the_same_sentence():
    assert mixed("Zrobiłem <en>commit</en> dziś.") == ["zrobiłem COMMIT dziś."]


def test_polish_ending_after_the_tag_has_no_space():
    assert mixed("Na <en>Python</en>ie.") == ["na PYTHONie."]


def test_new_sentences_of_a_part_stay_separate():
    assert mixed("Raz|dwa <en>three|four</en> pięć") == ["raz", "dwa THREE", "FOUR pięć"]


def test_polish_ending_followed_by_more_sentences_gets_the_stress():
    # The stress goes to the word at the junction, not to the last sentence of the part.
    assert mixed("Ja <en>push</en>ała|potem obiad|koniec") == ["ja PUSHˈała", "potem obiad", "koniec"]


def test_punctuation_after_the_tag_is_kept():
    # espeak-ng gives no phonemes for "." or for the "," before "do jutra".
    assert mixed("Zrobiłem <en>commit</en>.") == ["zrobiłem COMMIT."]
    assert mixed("<en>Good night</en>, do jutra.") == ["GOOD NIGHT, do jutra."]


def test_one_letter_preposition_before_a_span_is_not_read_as_a_letter_name():
    # Alone, espeak-ng reads "w" as "vɨ" and "z" as "zɨ". In a sentence, "w Pythonie"
    # is "f pɨtxˈɔɲʲɛ" and "z Johnem" is "z dʒˈɔnɛm": voiceless before a voiceless phoneme.
    assert mixed("Testy w <en>Python</en>.") == ["testy f PYTHON."]
    assert mixed("Z <en>Kate</en> i z <en>John</en>em.") == ["s KATE i z JOHNem."]
