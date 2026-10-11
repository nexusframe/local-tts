# English words in Polish speech: `<en>` tags

## Function

The Polish Piper voices read all text with Polish espeak-ng rules. English words then sound wrong.
Mark English words. The daemon then reads them with English phonemes that the Polish voices know,
and a Polish ending gets Polish stress.

```
Zrobiłem commit'a i wrzuciłem go na GitHub'a. Teraz trzeba to push'ować.
Testy w <en>Python</en>ie przeszły, ale <en>pipeline</en> jeszcze się buduje.
```

Use this for English words in Polish sentences only. For full English sentences, use an English voice:
a listening test (2026-10-10) rejected full English sentences in a Polish voice.

The protocol does not change. The tags are part of the `text` field of `speak` and `append`.

## Rules for the text (for the LLM prompt)

1. Put a tag around English words only. Do not tag Polish words. Do not tag full English sentences.
2. Inflect English words as Polish speakers do. Write the Polish ending after an apostrophe: `commit'a`, `GitHub'a`, `push'ować`. A word with an apostrophe and a Polish ending needs no tag. Without an apostrophe, write the ending after `</en>`: `<en>Python</en>ie`. For more than one word, use a tag: `<en>pull request</en>'a`.
3. Write acronyms in capital letters without spaces: `<en>API</en>`, `<en>USB</en>`. With spaces, `A` is read as the article "a". espeak-ng reads some short acronyms as words (`CI` like "sigh"). For these, use periods: `<en>C.I.</en>`.
4. Do not put tags inside tags. Do not write phonemes or `[[ ]]` blocks. Outside a span, the normalizer removes `[...]` text.

Example text for the system prompt of the assistant (`~/projects/local-assistant`):

> Your answer is read aloud by a Polish voice. Inflect English words as in spoken Polish and write the Polish ending after an apostrophe, for example "commit'a", "GitHub'a", "push'ować". Put other English words between `<en>` and `</en>`, for example `<en>pipeline</en>`. Write acronyms in capital letters without spaces, for example `<en>API</en>`.

## How it works

1. `normalizer/english.py`: `normalize()` puts a placeholder in place of each span before the Polish rules, and puts the span back at the end. The Polish rules (numbers, abbreviations, units, markup) do not change English text. Whitespace in a span becomes one space. An empty span and a `</en>` without `<en>` are removed. An `<en>` without `</en>` ends at the end of the text. A Latin word with an apostrophe and a Polish ending (`commit'a`) becomes `<en>commit</en>a`. The stem must have 2 or more letters (`o'clock` stays), and English contractions (`'s 't 're 've 'll 'd 'm`) stay. An apostrophe right after `</en>` is removed.
2. `splitter.py`: when a segment ends inside a span, the segment gets `</en>` and the next segment starts with `<en>`. This applies to `split_sentences()` and to the early first segment of `SentenceStream`. A sentence end next to a tag (`Hello.</en> Dalej`, `Gotowe. <en>Hi</en>`) is a boundary. For the early first segment, a tagged word is a plain word, so `Zrobiłem <en>commit</en> | i…` can be cut.
3. `backends/phonemes.py`, `phonemize_mixed()`: Polish parts go to Polish espeak-ng (with the "trz" fix). English parts go to espeak-ng `en-us`, then `to_polish_phonemes()` changes the English-only phonemes to the nearest Polish phonemes. The parts are joined in one sentence.
4. `backends/piper.py`: `PiperBackend` uses `phonemize_mixed()` for each voice. `PiperBackend.phonemize()` shows the phonemes of a text.

### Phoneme map

The Polish voices did not learn these English phonemes: `æ ð θ ɹ ɪ ʊ ʌ ə ɚ ɜ ɑ ɐ ɾ ᵻ h e o ː`.

| English | Polish | English | Polish |
|---|---|---|---|
| eɪ, aɪ, ɔɪ | ɛj, aj, ɔj | ɪ, ᵻ | ɨ |
| oʊ, aʊ | ɔw, aw | ɹ | r |
| ɚ | ɛr | ɾ | t |
| æ, ə, ɜ, e | ɛ | ʊ | u |
| ð | d | ʌ, ɑ, ɐ | a |
| θ | f | h | x |
| o | ɔ | ː | (removed) |

### Corrections at the span edges

- espeak-ng gives no phonemes for punctuation before the first word of a part. Punctuation right after `</en>` is kept as a phoneme, because the sentence intonation needs it.
- Alone, espeak-ng reads `w` and `z` as letter names (`vɨ`, `zɨ`). Before a span, they get the phonemes that espeak-ng gives in a sentence: `f`/`w` and `s`/`z` (voiceless before a voiceless phoneme).
- Alone, espeak-ng also reads the ending `y` as a letter name (`ˈiɡrɛk`). After a span, the ending goes to espeak-ng as `ty`, and then the `t` phoneme is removed (`commit'y` → `kɛmˈɨtɨ`). The other one-letter endings (`a e i o u ą ę ó`) are correct without a change (measured 2026-10-11).
- An English stem with a Polish ending is one Polish word: the stress goes to the second-to-last vowel of the full word (`push'ować` → `puʃˈɔvatɕ`, `commit'a` → `kɛmˈɨta`).

## Measured facts

- Listening test, 2026-10-10, 4 male voices and `zenski_wg_glos`: English with the phoneme map (`ipa_pl`) sounded better than raw English IPA and better than English words in Polish spelling. Samples: `scripts/listen_ipa.py`, `scripts/listen_male_voices.py`.
- Engine with a real voice (`meski_wg_glos`), text in pieces of 4 characters, 3 runs: TTFA 54–56 ms with tags, 63–80 ms for the same text without tags. No errors. Before the early-cut correction, TTFA with tags was 178–280 ms.
- Tests: `tests/test_normalizer_en.py`, `tests/test_splitter_en.py`, `tests/test_phonemes_en.py`, `tests/test_piper_en.py` (real model; skipped if the model is not downloaded).

## Limits

- The voice is Polish. English words sound like a Polish speaker says them. Full English sentences need an English voice.
- Short Polish prepositions alone before a span (`do`, `na`) get stress, because espeak-ng reads them alone.
- The daemon does not find English words without a tag or an apostrophe.
- Listening samples through the engine steps: `scripts/listen_en_tags.py`.
