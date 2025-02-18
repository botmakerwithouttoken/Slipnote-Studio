# Slipnote Studio

Below is the **Slipnote Studio** README in **Markdown** format, **without** the Python code snippet. It describes the main menu, `.slip` saving/browsing, the image-based top screen, bottom-screen buttons, multi-frame creation, onion skin, audio recording, a log display in the window, FPS selection, and microphone selection.

---

## Main Menu Image

![Slipnote Studio Main Menu](main_menu.png)

> **Note:** Save this image as **`main_menu.png`** in the same folder as your project.

---

## Overview

Slipnote Studio is a spiritual successor to Nintendo’s Flipnote Studio. It allows you to create simple frame-by-frame animations (called “slipnotes”), record 8-bit mono audio, and manage your slipnotes with a main menu interface:

1. **Create Slipnote**  
   - A creation interface where you can draw on the top screen (with brush or line tools), toggle onion skin, manage frames, record/play audio, and save your animations as `.slip` files.

2. **Browse Slipnotes**  
   - A browsing interface showing all `.slip` files in a `slipnotes/` folder. Select one to either **edit** (which loads it into the creation interface) or **convert** to `.mp4`/`.gif` (placeholder functionality).

### Key Features

- **Main Menu** with top-screen image (the green “Slipnote Studio” logo) and bottom-screen buttons:
  - **Create Slipnote**: Opens the creation mode.
  - **Browse Slipnotes**: Lists your existing `.slip` files.

- **Creation Mode**  
  - Multi-frame drawing with **onion skin**.  
  - **Brush** or **Line** tools.  
  - **Save** as `.slip` (using a simple pickle-based format).  
  - **Audio Recording**: 8-bit, mono, with PyAudio or a fallback “virtual mic” that generates random data.  
  - **FPS Selection** (1–30).  
  - **Microphone Device Selection** (if PyAudio is installed).

- **Browse Mode**  
  - Lists `.slip` files found in the **`slipnotes/`** folder.  
  - Selecting a slipnote lets you **edit** it or **convert** it to `.mp4` or `.gif` (placeholder logs only).

- **Logging**  
  - A log area at the bottom of the window displays info and error messages in real time.

---

## File Structure

A typical setup:

