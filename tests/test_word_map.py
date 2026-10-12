from local_tts.normalizer import normalize
from local_tts.word_map import heard_prefix


def test_heard_words_give_the_same_words_of_the_client_text():
    assert heard_prefix("Jutro będzie bardzo ciepło.", 2, normalize) == "Jutro będzie"


def test_a_number_counts_only_when_all_its_spoken_words_were_heard():
    text = "Założone w 1257 roku."
    # normalize: "Założone w tysiąc dwieście pięćdziesiąt siedem roku." -> the number is 4 words.
    assert heard_prefix(text, 5, normalize) == "Założone w"
    assert heard_prefix(text, 6, normalize) == "Założone w 1257"


def test_no_heard_word_gives_empty_text():
    assert heard_prefix("Jutro będzie ciepło.", 0, normalize) == ""


def test_the_prefix_does_not_cut_an_english_span():
    text = "Zrestartuj <en>engine x</en> teraz."
    assert heard_prefix(text, 2, normalize) == "Zrestartuj"
    assert heard_prefix(text, 3, normalize) == "Zrestartuj <en>engine x</en>"


def test_text_after_a_shorter_normalization_does_not_go_past_the_heard_words():
    # "ok" is "okej": same word count. "itd." is "i tak dalej": 3 words.
    assert heard_prefix("Ok, itd. i koniec.", 3, normalize) == "Ok,"
