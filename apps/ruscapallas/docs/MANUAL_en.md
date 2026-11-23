# RuscaPallas — manual

Pallasio is an old, learned and embittered Pallas's cat, with a cream jacket, a red tie, small round glasses and a tome always in hand. He lives shut in a storage closet and, through a window, watches a world run by zombies and pigs, pondering the meaning of life and the absurdity of it all. He walks on the desktop, jumps on windows and, if you click him, listens and answers aloud.

He listens, thinks and speaks with the same engines as RuscaLLisse: ruscavosk-engine (Vosk), ruscallama-engine (llama.cpp) and ruscapiper-engine (Piper).

## First time

1. Pallasio uses the same files as RuscaLLisse: a Vosk model to listen, a GGUF model to think and a Piper voice. If RuscaLLisse works, Pallasio works too; otherwise open RuscaLLisse and follow “Which files to download?”. For a male Italian voice, download `it_IT-riccardo-x_low`.
2. After installing the package, log out and back in: GNOME only sees new extensions at login.
3. Open **RuscaPallas** from the RuscaLinux Apps folder: Pallasio appears at the bottom of the screen and his window opens.

## Talking to him

- **Click** Pallasio: he crosses his arms, raises an eyebrow and listens. The bubble shows an ear.
- Ask your question. While thinking he sits down and checks his tome (bubble with dots), then answers with a snarl and a wagging finger (bubble with waves).
- After answering he keeps listening for a few seconds. If you stay silent, he huffs and goes back to walking.
- **Click** while he speaks or listens: he goes quiet.
- The first time he takes a few seconds to wake up (bubble with an hourglass): he is loading the models.

The bubble never shows words: the conversation is not written and not saved.

## Moving him

- **Drag** him with the mouse; when released he falls to the ground, or onto the window below.
- **Right click**: “Quiet” and “Back to the closet”. Open RuscaPallas again to call him back.
- He is not shown in the Activities overview or over full-screen windows.
- With animations turned off (Settings → Accessibility) he stands still, but still talks.

## The RuscaPallas window

Open it from the RuscaLinux Apps folder. **Talk** (Ctrl+T) makes Pallasio prick up his ears without looking for him on the desktop. Below are the settings:

- **On the Desktop:** show him or send him back to the closet; size (small, normal, large); how often he jumps on windows (never, sometimes, often); whether he sits down to read on his own. They apply at once.
- **Conversation:** how long he keeps listening after answering (4, 8 or 15 seconds); short, normal or long answers; emotions on his face. They apply from the next question.
- **Models and Voice:** to listen, to think, the voice and its speed, the graphics card. “Same as RuscaLLisse” uses the same files as RuscaLLisse. They apply from the next conversation.
- **Personality:** “Edit Personality…” opens his character file, `~/.local/share/ruscapallas/pallasio.md`, with the same sections as RuscaLLisse entities (Quid, Character, Way of speaking, Never does, Voice); changes apply from the next question. “Restore the Original Pallasio…” puts back the one in the package.
- **Appearance:** the window theme.

Settings are kept in `~/.config/ruscapallas/settings.json`. A voice and speed chosen in the window win over those written in the personality.

## From a terminal

    ruscapallas            opens the window and calls him back
    ruscapallas --show     calls him back, without the window
    ruscapallas --hide     sends him back to the closet
    ruscapallas --quit     stops the dialogue service and frees memory

The dialogue service starts at the first click and quits by itself after fifteen minutes without conversation. To see the timing of each turn and what he understood: `ruscapallas --quit`, then start the service by hand with `RUSCALLISSE_DEBUG=2 /usr/share/ruscapallas/ruscapallas-service.py` and click Pallasio.

## Privacy

Everything stays on this computer. The language model only listens on 127.0.0.1; audio is never saved; the conversation stays in memory and is forgotten when the service quits. Pallasio only looks at window edges to walk on them: he does not read what they contain. He is a character, not an expert: check his answers.
