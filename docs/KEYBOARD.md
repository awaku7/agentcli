# CLI Keyboard Reference

Keys for the interactive CLI (`uag`). Unless a section says
otherwise, they work both in the default full-screen view and in
the legacy prompt (`UAGENT_CLI_VIEW=0`).

## Sending a message

| Key | What it does |
| --- | --- |
| Enter | Send the line |
| Ctrl+J | Insert a line break, to write a multi-line message (full-screen view only; in the legacy prompt Ctrl+J sends, like Enter) |
| Paste (Ctrl+V / right-click, terminal permitting) | Inserts the pasted text; nothing is sent until you press Enter |

While the agent is working, the full-screen view keeps the input
line live:

- Pressing Enter on a message asks what to do: press Enter again
  (or `y`) to interrupt the response and send now, or `n` to
  queue the message for the next turn. Esc, or Ctrl+C, also
  queues it.
- Lines starting with `:` are commands; they are queued without
  asking.
- Queued messages are shown in the output area as waiting, and
  are sent in order.

To write a long message in an editor instead, send a line
containing only `f`. In the editor, Ctrl+X sends and Esc
cancels.

## Editing the input line

The input line uses Emacs-style editing keys:

| Key | What it does |
| --- | --- |
| Ctrl+A / Ctrl+E | Go to the start / end of the line |
| Ctrl+B / Ctrl+F | Move one character left / right |
| Alt+B / Alt+F (or Esc, then B / F) | Move one word left / right |
| Ctrl+K | Delete from the cursor to the end of the line |
| Ctrl+U | Delete from the cursor to the start of the line |
| Ctrl+W, or Alt+Backspace | Delete the word before the cursor |
| Ctrl+Y | Insert the last deleted text back |
| Ctrl+T | Swap the two characters around the cursor |
| Ctrl+_ | Undo the last edit |
| Ctrl+L | Redraw the screen |

## Completion

- Tab opens the completion menu: `:` commands, file paths, and
  other candidates for the word being typed.
- Candidates also appear on their own while you type.
- In the menu, Up / Down move, Tab cycles, and Enter uses the
  highlighted candidate.

## Input history

- Up / Down at the input line browse the messages you sent
  earlier.
- Ctrl+R incremental history search is not available in the
  full-screen view.

## Reading the output (full-screen view)

| Key / action | What it does |
| --- | --- |
| PageUp / PageDown | Scroll the output area |
| Mouse wheel | Scroll the output area, wherever the pointer is |
| Drag with the mouse | Select output text; releasing the button copies it to the clipboard. Holding the pointer at the top or bottom edge keeps scrolling while you select |

## Stopping and exiting

| Key | What it does |
| --- | --- |
| F12 | Interrupt the running response (also stops Auto-pilot) |
| Ctrl+C | While a response is running: interrupt it. While a question is waiting: cancel the question instead. While idle: exit the CLI |
| Ctrl+D | On an empty input line: exit the CLI |

## Answering questions

Sometimes the agent asks a question — a confirmation, a choice,
or a password. In the full-screen view the screen does not
switch: the question stays in the output, the top border shows
`[REPLY]` (or `[PASSWORD]` for a password), and you type the
answer in the same input line.

- Enter sends the answer. Ctrl+C cancels the question.
- A message you had half-typed when the question appeared comes
  back after you answer.
- Password answers are shown as `*` while you type. They are
  never kept in the input history, and editing keys that could
  carry the text elsewhere (undo, cut, macros) cannot bring a
  password back afterwards.
- For a long answer, send a line containing only `f` to open
  the multi-line editor (Ctrl+X sends, Esc cancels).

## Keyboard macros

A macro records a sequence of keystrokes and replays it later —
handy for a series of keystrokes you repeat within one session.

| Key | What it does |
| --- | --- |
| Ctrl+X ( | Start recording |
| Ctrl+X ) | Stop recording |
| Ctrl+X e | Replay the recorded keystrokes |

Example: press Ctrl+X (, type `:cd src` and Enter, then press
Ctrl+X ). From then on, Ctrl+X e repeats those keystrokes.

Macros are kept only for the current session; they are not
saved when the CLI exits. Only the most recent macro is kept —
recording a new one replaces it. While you answer a password
question, recording is paused and anything recorded during the
answer is discarded, so a password can never end up in a macro.
