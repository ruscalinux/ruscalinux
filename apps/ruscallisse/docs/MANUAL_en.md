# RuscaLLisse — manual

A voice conversation with Ellittica, an intellectual, gentle and sensitive digital woman who explains things simply. It is a conversation like in real life: only her face is on screen, nothing is written and the conversation is not saved.

**Test version.** The engines to listen (Vosk) and to speak (Piper) are the prebuilt ones of the official packages, in `/usr/lib/ruscallisse/prova/`.

## First time

Three things are needed, and RuscaLLisse does not download them (main menu → "Which Files to Download?"):

1. **A model to listen (Vosk):** unzipped into `~/.local/share/ruscavosk/models/`.
2. **A model to think (GGUF):** the same as RuscaLLama, in `~/.local/share/ruscallama/models/`.
3. **A voice (Piper):** the two files `name.onnx` and `name.onnx.json`; main menu → "Import a Voice…".

Then, from the main menu, "Edit Personality…": write Ellittica's **quid**, the core trait of her character.

## Talking

- Speak normally: Ellittica listens, thinks and answers aloud.
- **Space** pauses and resumes the microphone.
- **Esc** makes her stop.
- **Ctrl+N** starts over: she forgets the conversation.

While she speaks the microphone does not listen, so she does not hear herself.

## Privacy

Everything stays on this computer. The language model listens only on 127.0.0.1; audio is never saved; the conversation stays in memory and is forgotten when the window closes. Every model and voice has its own license. Ellittica is a character, not an expert: check her answers.

## For developers

`RUSCALLISSE_DEBUG=1 ruscallisse` prints the timing of each turn; `RUSCALLISSE_DEBUG=2` also what was understood and the answer.
