# Prosody

## Definition

Prosody is how a speaker says words: the melody, the rhythm and the stress of speech. Prosody gives emotion, intent and meaning to an utterance.

Prosody has these parts:

| Part | Description |
|---|---|
| Intonation | The pitch of the voice goes up and down. |
| Stress | The speaker makes some syllables or words stronger. |
| Tempo and rhythm | The speed of speech and how the utterance is divided in time. |
| Pauses | Breaks that give structure to the utterance or make tension. |
| Loudness | Changes in the volume of the voice. |

## Example

The sentence „Ty to zrobiłeś” can be a question, an accusation or admiration. Only prosody makes the difference.

Stress on one word changes the meaning: „TY to zrobiłeś” tells the listener who did the action.

## Relation to this project

Measured facts:

- In the M0 listening test, Piper `zenski_wg_glos-medium` got 3.20 for prosody. Supertonic 3 M1 got the highest prosody score, 3.60. See `docs/m0-decision.md` section 8.
- Piper 1.8.0 `SynthesisConfig` has these fields: `speaker_id`, `length_scale`, `noise_scale`, `noise_w_scale`, `normalize_audio`, `volume`. It has no pitch or stress control.

What Piper can control for each segment:

| Part | Control in Piper |
|---|---|
| Tempo | Yes: `length_scale` |
| Pauses | Yes: the daemon adds silence between segments |
| Loudness | Yes, for a full segment: `volume` |
| Intonation | No. The model selects it from the text and punctuation. |
| Stress on one word | No. To split a sentence in the middle breaks its intonation. |

Assumptions:

- Punctuation changes the intonation of Piper (for example, „?” gives a question melody). This is not measured.
- Control of intonation, stress and emotion needs an expressive TTS model. No candidate in `research.md` has good Polish, real-time speed on CPU and style control together.

Related idea: lector tags such as `[pauza]`, `[wolniej]` and `[szeptem]`. This is a possible milestone after M2. It is not in M1.
