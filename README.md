# Introducing Lumo Voice Preview

Tired to talk with Lumo?

Let Lumo talk with you

<img src="lumo_voice.png" width="300" height="250">


This guide explains how to **send questions to a local Lumo Api V2 service**  and **play the spoken response on a Home Assistant Voice Preview device** using Piper TTS.

The Lumo server (`lumo.js`) is assumed to already be installed and running locally.

Please refer to the [Lumo Api V2 installation](https://github.com/carlostkd/Lumo-Api-V2)
  
This tutorial focuses only on **Home Assistant +  scripts configuration**.

All other software like **whisper** and **piper** is not covered by this tutorial you need to follow the installation instructions of that softwares  for your machine.

---

## Overview



1. You type a question using the cli script or HA button

2. The Python script sends the question to Lumo (`localhost:3333`)

3. Lumo returns a text response

4. Home Assistant speaks the response using **Piper TTS**

5. Audio is played on the [**Voice Preview device** ](https://www.home-assistant.io/voice-pe/)

6. You can set your desired voice. Refer to piper voices for this i dont cover that in this tutorial time is precious sorry.

No cloud services are required. **Privacy Please!**

---

## Requirements

- Home Assistant Core or OS installed
- A working[ **Voice Preview** device](https://www.home-assistant.io/voice-pe/) 
- Piper TTS already configured in Home Assistant
- Lumo Api V2 server running locally (`http://localhost:3333`)
- A Long-Lived Access Token from Home Assistant

---

## Step 1 – Create a Home Assistant Access Token

1. Go to **Profile → Security**
2. Create a **Long-Lived Access Token**
3. Copy it and store it securely

Add it to your `secrets.yaml`:

```yaml
assist_button_token: YOUR_LONG_LIVED_TOKEN_HERE
```

## Step 2 

- Find Your Voice Preview Media Player Entity

Go to Developer Tools → States
Search for media_player
Look for something like:

media_player.home_assistant_voice_xxxxxx_media_player

## Step 3 - Verify Your TTS Entity

Probably you will have Piper as:

`tts.piper`

To confirm:
Go to Developer Tools → Services
Search for tts.speak
Check the available TTS providers
If your TTS entity is different, note it.

## Step 4 – Configure the Python Script

In the script, replace only these two values:

```
TTS_ENTITY = "tts.piper"
MEDIA_PLAYER = "media_player.YOUR_VOICE_PREVIEW_ENTITY"
```
 
## Step 5 – How it Works

`chmod +× lumo.py`
```

./lumo.py "Why is the sky blue?"
```

The script will:

Send the question to http://localhost:3333

Receive Lumo’s text response

Clean UI noise automatically

Call Home Assistant’s tts.speak

Play audio on the Voice Preview device

With you desired voice.

**Pros :**

Can run in a device with limited resources like rpi 4 or 5

Everyting stays private its your hardware (voice preview)

Lumo itself is private no trainings no sell prompts.

**Cons:** 
Does not works very well do perform activities on the web its possible to enable the websearch but because the trash that Proton introduces on the response feed like **"searched the web for" .... bla bla** this makes the responses takes longer and spoken urls is also not what we want definitely. 


# Home Assistant – Dashboad + Text Button → Voice Speak

This guide shows how to create a Home Assistant Button with:
- a text input (`input_text.lumo_prompt`)
- a button that runs `lumo.py`
- the response is spoken on Home Assistant Voice via Piper 

---

## 1) Create the Text Helper (input field)

1. Go to **Settings → Devices & Services → Helpers**
2. Click **Create Helper**
3. Choose **Text**
4. Configure:
   - **Name:** `Lumo Prompt`
   - **Entity ID:** `input_text.lumo_prompt`
   - **Max length:** `255`
5. Save

---

## 2) Add the Shell Command

Edit `configuration.yaml` and add (or merge into your existing `shell_command:` block):

```yaml
shell_command:
  lumo_ask: /usr/bin/python3 /your_file_path/lumo.py
  ### verify your python path and lumo.py path
```

Note if you already have a** "shell_command"** on the yaml dont duplicate it...
In that case just add:

** lumo_ask: /usr/bin/python3 /your_file_path/lumo.py** under your other shell_command

After restart, confirm the service exists:
- **Developer Tools → Services**
- Search for: `shell_command.lumo_ask`

---

## 3) Create the Script that calls the Shell Command

Edit `scripts.yaml` and add:

```yaml
lumo_ask_speak:
  alias: Ask Lumo and Speak
  mode: single
  sequence:
    - choose:
        - conditions:
            - condition: template
              value_template: "{{ states('input_text.lumo_prompt') | trim | length > 0 }}"
          sequence:
            - service: shell_command.lumo_ask
      default: []
```

Then reload scripts:
- **Developer Tools → YAML → Reload scripts**

---

## 4) Create the Dashboard UI

### A) Add the input field card
1. Edit your dashboard
2. Add a card → **Entities**
3. Add entity:
   - `input_text.lumo_prompt`
4. Save

### B) Add the button card
1. Add a card → **Button**
2. Set:
   - **Name:** `Ask Lumo`
3. Under **Tap action**:
   - Action: **Call service**
   - Service: `script.lumo_ask_speak`
4. Save

---

## 5) Permissions (required for HA Core)

`homeassistant` must be able to traverse your home directory and execute the script.

Run:

```bash
sudo chmod o+x /home/JustinCase # replace with your username and stop using my username
sudo chmod 755 /home/your_username/lumo.py
```

Verify as the `homeassistant` user:

```bash
sudo -u homeassistant /usr/bin/python3 /home/your_username/lumo.py "hello"
```

---

## How it works

1. You type a question into `input_text.lumo_prompt`
2. You press the dashboard button
3. Home Assistant runs `shell_command.lumo_ask`
4. `lumo.py` reads `input_text.lumo_prompt`, calls your local Lumo endpoint, and uses HA `tts.speak` to play the response on Home Assistant Voice
5. Choise your desired voice for Lumo.
Done.


## Send questions to Lumo without Button

To send questions to Lumo without Dashboard Button use the same file lumo.py
Usage:
    `lumo.py "Hello how are you" ` 

## Internet queries in a secure way 

## Please Note:

This script was fully tested with the Ollama Model:

`qwen3:4b-instruct` which also works to **full control the HA instance** if the entities are exposed

**If you use other Model this may or may not works.**

To use Internet queries in a Secure way use the script ollama.py

Make sure you have Ollama configured somewhere and is running in your HA

This tutorial does not cover that steps - Time is precious....

open the script ollama.py and replace the lines:

###  TTS / output device
AGENT_ID = "your_agent_id"
TTS_ENTITY = "tts.piper" # whatever your tts is
MEDIA_PLAYER = "media_player.home_assistant_voice_0xxxxx_media_player" # your media player id

###  Run the script :

`python3 ollama.py`

The script aks you for a url from where you want the last news

and how many articles to read 

enter a desired url ex: https://proton.me/blog

enter the amount of news ex: 5

or when the script launches just press enter to default the Hacker News with the last 12 articles.

Enjoy!

Fill free to contribute with improvements or suggestions.
