# Embodied Fo

Fo (Wajo's agent) running on a Reachy Mini. Voice in → Fo thinks → voice
out, with head motion and emotion animations that match the tone of each
reply.

## Demo

The code is a general Fo client, anything Fo can do works through it.
For the demo video, I walk through a gift-choosing flow with Fo: I ask
it to help me find a gift, Fo looks it up and texts the
options to my phone, and I decide which one with it. I ask it to add it in my basked with adding a gift note. The whole thing is
voice-only through the robot.

## How to run

### Prerequisites

- A Reachy Mini robot (Wireless or Lite), **or** the MuJoCo simulator if
  you don't have hardware
- Python 3.10–3.12 (3.12 recommended)
- A [Wajo](https://wajo.ai) account — you'll be prompted to grant OAuth
  access on first run; SMS integration must be enabled on your account
  for the "text me the details" flow to land

### 1. Install the Reachy Mini SDK and start the daemon

Follow Pollen Robotics' installation guide:
👉 **[Reachy Mini SDK — Installation](https://huggingface.co/docs/reachy_mini/SDK/installation)**

Here is their original Reachy Mini SDK Github link: https://github.com/pollen-robotics/reachy_mini

Once the SDK is installed, start the daemon so this app can talk to the
robot. Pick one:

| Setup | Command |
| --- | --- |
| **Reachy Mini (Wireless)** | Already running when the robot is powered on |
| **Reachy Mini Lite (USB)** | `reachy-mini-daemon` |
| **Simulation (Linux/Windows)** | `reachy-mini-daemon --sim` |
| **Simulation (macOS)** | `mjpython -m reachy_mini.daemon.app.main --sim` |

Verify the daemon is up by opening http://localhost:8000/docs (or
http://reachy-mini.local:8000/docs on Wireless). You should see the SDK's
API documentation.

> **Note:** The daemon stays running in its own terminal — keep that
> window open while you run this app.

### 2. Install and run embodied_fo

In a **new terminal** (keep the daemon running in the first):

```bash
# Clone and enter the project
git clone https://github.com/yaseminozkut/embodied_fo.git
cd embodied_fo

# Create and activate a Python 3.12 venv
python3.12 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run
python -m embodied_fo.main
```

### OAuth

When you run, a browser tab opens for Wajo sign-in. Click
**Allow** so that Wajo (Fo) MCP connects.

### Using it

Once you see `Ready. Just talk — Ctrl-C to exit.`, in your terminal, just speak. The robot
listens continuously (Silero VAD), transcribes locally
(faster-whisper), sends the text to Fo over MCP, and speaks back with Edge TTS.

Ctrl-C to exit — the app signs you out and cleans up on shutdown.

## What it does: FO EMBODIED IN AN EXPRESSIVE ROBOT

The robot listens you continuously using voice activity detection
(`Silero VAD`). A 1.5 second pause
ends your turn. Your speech is then transcribed locally with
`faster-whisper` and sent to Fo (Wajo's agent) over MCP. Fo is the
brain of this robot. It does what it does originally: answers your question, calls tools (SMS, email,
purchases, calendar, etc.), and doing its magic on your behalf to
get things done.

Because the robot speaks its replies aloud, Fo is adapted for a
speaking context!!! Normally when you chat with Fo on the web, replies
can be long and full of links. But reading a URL out loud sounds
terrible *"h-t-t-p-s w w w dot..."* so a short prompt
tells Fo to keep spoken replies to a few sentences and send any links
by SMS instead. You hear a quick summary from the robot, and the
details sent to your phone.

The robot is also expressive at every stage of the conversation:

- **Idle**: gentle antenna sway.
- **Thinking**: the head tilts the moment you stop talking
- **Reacting**: Fo picks an emotion from a list of 12
  (`cheerful`, `inquiring`, `surprised`, `understanding`, etc.) based
  on the tone of what it's about to say. The robot plays that
  emotion, a recorded move with its own sound from pollen robotics library, right before
  speaking the reply.
- **Talking**: the head gently wobbles in sync with Ava's voice
  while she delivers the reply.

## Limitations & what I'd build next

**MCP is slow and non-streaming.** Fo's MCP endpoint returns the full
reply at once, no streaming, and in practice calls take a noticeable
moment even for simple requests like "Hæi Fo." 

Two things I'd do here if I had the access:

- *Try a faster transport.* Calling Fo over the phone
  seems to return much faster than MCP in practice. If Wajo exposed
  other endpoints for that, or any transport that
  responds faster, I'd route through that. Right now MCP is the only
  option available to me.
- *Stream partial replies.* `get_fo_reply` over MCP only returns the
  final full response at the end. The chunks generated during the
  request get combined server-side and delivered as a single output,
  not mid-stream. I'd rather speak each chunk as soon as it arrives,
  the way Fo's own chat interface already does. MCP doesn't allow
  that, but if a Fo API that supports streaming becomes
  available I'd definitely apply that which would make the robot
  feel a lot more alive and the user knows whats going on and what's Fo doing.

**Face tracking with the camera:** Reachy Mini has a camera I never
wired in. If I had more time, I'd run a face detector on the feed and
have the head turn toward whoever's talking. The embodiment would feel
much more real when the robot visibly sees you, not just hears you.

**Interruption:** Right now the user has to wait for the
robot to finish speaking before saying anything. I'd rather keep the
mic active during TTS so VAD can catch the user interrupting and the
robot would stop talking mid-reply and start listening. That needs
echo cancellation so the robot doesn't hear its own voice as a user
interrupt.

**Expose the robot as its own MCP server.** Right now the robot is
only an MCP client to Fo. If I also ran an MCP server that hosts
the robot's capabilities as tools, `play_emotion`, `play_move`,
`look_at`, etc., and connected it to Wajo, Fo could discover and
call them directly. Fo would just call
`play_emotion("cheerful1")` as a tool. 
Fo could compose richer behaviors.
Needs Fo on Wajo's side to be configured to use external MCP tools.