import sys
import os
import pygame
from pygame.locals import *
import threading
import time
import random
import logging

# Configure logging to use our custom handler (which displays in the window)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# For file dialogs, microphone selection, and other dialogs
import tkinter as tk
from tkinter import filedialog, simpledialog

# For loading the icon and images via Pillow
from PIL import Image

# Try to import PyAudio
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    logging.error("PyAudio not found. Using VirtualMicrophone.")
    PYAUDIO_AVAILABLE = False

import wave

# For exporting to GIF or MP4, you might use imageio or moviepy, but here we just log success.
# If you want real exports, install something like `imageio` or `moviepy`.
# pip install imageio moviepy

# Custom logging handler to store messages for display in the Pygame window
class PygameLogHandler(logging.Handler):
    def __init__(self, studio, capacity=10):
        super().__init__()
        self.studio = studio
        self.capacity = capacity

    def emit(self, record):
        msg = self.format(record)
        self.studio.log_messages.append(msg)
        if len(self.studio.log_messages) > self.capacity:
            self.studio.log_messages.pop(0)

class VirtualMicrophone:
    """
    Simulates a microphone by generating random 8-bit audio data.
    Single-channel (mono).
    """
    def __init__(self, chunk=1024, rate=44100):
        self.chunk = chunk
        self.rate = rate

    def read(self, size):
        # Generate random bytes (0–255) for 8-bit audio
        return bytes(random.randint(0, 255) for _ in range(size))

class SlipnoteStudio:
    def __init__(self):
        # Make sure there's a slipnotes folder
        os.makedirs("slipnotes", exist_ok=True)

        pygame.init()
        pygame.mixer.init()

        # Window size: 400x600 to accommodate log area
        self.window_width, self.window_height = 400, 600
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("Slipnote Studio")

        # Load icons/images
        self.load_favicon(r"C:\Users\CCE\Downloads\16271246.png")
        self.load_main_menu_image(r"C:\Users\CCE\Pictures\Capture.JPG")  # The green Slipnote Studio image

        # Logging area
        self.log_messages = []
        self.font = pygame.font.SysFont("Arial", 14)
        self.log_area_rect = pygame.Rect(0, 482, self.window_width, self.window_height - 482)

        # Add a custom logging handler to display logs in the window
        log_handler = PygameLogHandler(self, capacity=10)
        log_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logging.getLogger().addHandler(log_handler)

        # State management: "main_menu", "create", "browse"
        self.state = "main_menu"

        # For the main menu, define button rectangles on the bottom screen
        # We'll place them side-by-side for demonstration
        self.btn_create_rect = pygame.Rect(50, 242 + 80, 120, 40)  # x, y, w, h
        self.btn_browse_rect = pygame.Rect(230, 242 + 80, 120, 40)

        # Create-mode data
        #  - frames for drawing
        #  - onion skin
        #  - audio recording, etc.
        self.frames = [pygame.Surface((400, 240))]
        self.current_frame = 0
        self.onion_skin = False

        self.top_screen = self.frames[self.current_frame]
        self.bottom_screen = pygame.Surface((400, 240))
        self.top_screen.fill((255, 255, 255))
        self.bottom_screen.fill((255, 255, 255))

        self.drawing = False
        self.last_pos = None
        self.pen_color = (0, 0, 0)
        self.tool_mode = 'brush'
        self.line_backup = None
        self.line_start = None

        # For storing slipnotes in .slip files
        self.slipnote_folder = "slipnotes"
        self.selected_slip = None  # for editing

        # Audio attributes
        self.loaded_audio_path = None
        self.is_recording = False
        self.audio_thread = None
        self.audio_file = "recorded.wav"

        # Microphone selection
        self.use_virtual_mic = not PYAUDIO_AVAILABLE
        self.selected_device = 0

        # FPS
        self.fps = 30
        self.clock = pygame.time.Clock()

        logging.info("Slipnote Studio started. Press 'F' to set FPS, or 'S' to select microphone.")
        self.run()

    # -------------------------------------------------------------------------
    # LOAD IMAGES
    # -------------------------------------------------------------------------
    def load_favicon(self, path):
        """Load favicon using Pillow and set it as the window icon."""
        try:
            im = Image.open(path).convert("RGBA")
            icon_surface = pygame.image.fromstring(im.tobytes(), im.size, "RGBA")
            pygame.display.set_icon(icon_surface)
        except Exception as e:
            logging.error("Could not load favicon. Using default icon. Error: %s", e)

    def load_main_menu_image(self, path):
        """Load the main menu top-screen image (the green Slipnote Studio image)."""
        try:
            im = Image.open(path).convert("RGBA")
            self.main_menu_image = pygame.image.fromstring(im.tobytes(), im.size, "RGBA")
        except Exception as e:
            logging.error("Could not load main menu image. Error: %s", e)
            self.main_menu_image = None

    # -------------------------------------------------------------------------
    # MAIN LOOP
    # -------------------------------------------------------------------------
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                    self.is_recording = False
                    break

                elif event.type == KEYDOWN:
                    # Common keys for any state
                    if event.key == K_f:
                        self.select_fps()
                    elif event.key == K_s:
                        self.select_microphone()

                    # Handle states
                    if self.state == "create":
                        self.handle_create_keys(event)
                    elif self.state == "browse":
                        self.handle_browse_keys(event)

                elif event.type == MOUSEBUTTONDOWN:
                    if self.state == "main_menu":
                        self.handle_main_menu_click(event.pos)
                    elif self.state == "create":
                        self.handle_create_mouse_down(event.pos)
                    elif self.state == "browse":
                        self.handle_browse_mouse_down(event.pos)

                elif event.type == MOUSEBUTTONUP:
                    if self.state == "create":
                        self.handle_create_mouse_up(event.pos)
                    # For browse, no special MOUSEBUTTONUP needed
                elif event.type == MOUSEMOTION:
                    if self.state == "create":
                        self.handle_create_mouse_motion(event.pos)

            # DRAW
            self.screen.fill((200, 200, 200))

            if self.state == "main_menu":
                self.draw_main_menu()
            elif self.state == "create":
                self.draw_create()
            elif self.state == "browse":
                self.draw_browse()

            # Draw the log area
            pygame.draw.rect(self.screen, (50, 50, 50), self.log_area_rect)
            y_offset = self.log_area_rect.top + 5
            for msg in self.log_messages:
                text_surface = self.font.render(msg, True, (255, 255, 255))
                self.screen.blit(text_surface, (5, y_offset))
                y_offset += self.font.get_linesize()

            pygame.display.flip()
            self.clock.tick(self.fps)

        pygame.quit()

    # -------------------------------------------------------------------------
    # STATE: MAIN MENU
    # -------------------------------------------------------------------------
    def draw_main_menu(self):
        """Draw the main menu (top screen image + bottom screen with two buttons)."""
        # Top screen: the main_menu_image
        if self.main_menu_image:
            self.screen.blit(self.main_menu_image, (0, 0))  # top-left corner
        else:
            # fallback if no image
            pygame.draw.rect(self.screen, (0, 255, 0), (0, 0, 400, 240))
            text_surf = self.font.render("Slipnote Studio", True, (255, 255, 255))
            self.screen.blit(text_surf, (100, 100))

        # Bottom screen: two buttons
        pygame.draw.rect(self.screen, (180, 180, 180), (0, 242, 400, 240))

        # Create Slipnote button
        pygame.draw.rect(self.screen, (255, 255, 255), self.btn_create_rect)
        create_label = self.font.render("Create Slipnote", True, (0, 0, 0))
        cx = self.btn_create_rect.centerx - create_label.get_width() // 2
        cy = self.btn_create_rect.centery - create_label.get_height() // 2
        self.screen.blit(create_label, (cx, cy))

        # Browse Slipnotes button
        pygame.draw.rect(self.screen, (255, 255, 255), self.btn_browse_rect)
        browse_label = self.font.render("Browse Slipnotes", True, (0, 0, 0))
        bx = self.btn_browse_rect.centerx - browse_label.get_width() // 2
        by = self.btn_browse_rect.centery - browse_label.get_height() // 2
        self.screen.blit(browse_label, (bx, by))

    def handle_main_menu_click(self, pos):
        """Check if user clicked 'Create Slipnote' or 'Browse Slipnotes'."""
        if self.btn_create_rect.collidepoint(pos):
            logging.info("Create Slipnote button clicked.")
            self.state = "create"
        elif self.btn_browse_rect.collidepoint(pos):
            logging.info("Browse Slipnotes button clicked.")
            self.state = "browse"

    # -------------------------------------------------------------------------
    # STATE: CREATE (drawing/editing slipnotes)
    # -------------------------------------------------------------------------
    def draw_create(self):
        """Draw the create slipnote interface (top screen is drawing, bottom is empty)."""
        # Onion skin
        if self.onion_skin and self.current_frame > 0:
            prev_frame = self.frames[self.current_frame - 1].copy()
            prev_frame.set_alpha(100)
            self.screen.blit(prev_frame, (0, 0))
        else:
            self.screen.blit(self.top_screen, (0, 0))

        pygame.draw.line(self.screen, (0, 0, 0), (0, 240), (400, 240), 2)
        self.screen.blit(self.bottom_screen, (0, 242))

    def handle_create_keys(self, event):
        """Handle key presses in the create slipnote mode."""
        if event.key == K_n:
            self.add_frame()
        elif event.key == K_LEFT:
            self.previous_frame()
        elif event.key == K_RIGHT:
            self.next_frame()
        elif event.key == K_o:
            self.onion_skin = not self.onion_skin
        elif event.key == K_c:
            self.clear_current_frame()
        elif event.key == K_p:
            self.play_animation()
        elif event.key == K_b:
            self.tool_mode = 'brush'
            logging.info("Tool mode set to Brush.")
        elif event.key == K_l:
            self.tool_mode = 'line'
            logging.info("Tool mode set to Line.")
        elif event.key == K_r:
            self.toggle_recording()
        elif event.key == K_k:
            self.play_recorded_audio()
        elif event.key == K_u:
            self.load_audio()
        elif event.key == K_m:
            self.play_loaded_audio()
        elif event.key == K_s:
            # Overload 'S' if you want to save slip, or you can choose another key
            self.save_slipnote_dialog()

    def handle_create_mouse_down(self, pos):
        """Handle mouse button down in create mode."""
        if pos[1] <= 240:
            if self.tool_mode == 'brush':
                self.drawing = True
                self.last_pos = pos
            elif self.tool_mode == 'line':
                self.line_start = pos
                self.line_backup = self.top_screen.copy()

    def handle_create_mouse_up(self, pos):
        """Handle mouse button up in create mode."""
        if self.tool_mode == 'brush':
            self.drawing = False
        elif self.tool_mode == 'line' and self.line_start is not None:
            pygame.draw.line(self.top_screen, self.pen_color, self.line_start, pos, 2)
            self.line_start = None
            self.line_backup = None

    def handle_create_mouse_motion(self, pos):
        """Handle mouse motion in create mode."""
        if self.tool_mode == 'brush' and self.drawing:
            if pos[1] <= 240:
                pygame.draw.line(self.top_screen, self.pen_color, self.last_pos, pos, 2)
                self.last_pos = pos
        elif self.tool_mode == 'line' and self.line_start is not None:
            self.top_screen.blit(self.line_backup, (0, 0))
            if pos[1] <= 240:
                pygame.draw.line(self.top_screen, self.pen_color, self.line_start, pos, 2)

    # Saving/loading .slip
    def save_slipnote_dialog(self):
        """Prompt the user for a .slip filename, then save the current frames."""
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".slip",
            filetypes=[("Slipnote files", "*.slip")],
            initialdir=self.slipnote_folder,
            title="Save Slipnote"
        )
        root.destroy()
        if file_path:
            self.save_slipnote(file_path)
            logging.info(f"Slipnote saved to {file_path}")
        else:
            logging.info("Save cancelled.")

    def save_slipnote(self, file_path):
        """
        Simple approach: store each frame as raw pixels or compressed string.
        For demonstration, we’ll just store the number of frames and the color of each pixel.
        This is not a real robust format—just an example.
        """
        import pickle
        # Convert frames to raw data
        frame_data = []
        for frame in self.frames:
            # Get raw pixel data
            pixels = pygame.image.tostring(frame, "RGBA")
            frame_data.append(pixels)
        slip_info = {
            "num_frames": len(self.frames),
            "width": 400,
            "height": 240,
            "frames_rgba": frame_data,
        }
        with open(file_path, "wb") as f:
            pickle.dump(slip_info, f)

    # -------------------------------------------------------------------------
    # STATE: BROWSE (view existing .slip files, click to edit/convert)
    # -------------------------------------------------------------------------
    def draw_browse(self):
        """
        Display a simple list of .slip files in self.slipnote_folder on the top screen.
        If the user has selected one, show options to edit or convert (mp4/gif).
        """
        # We'll just fill the top screen with a white background and list the files
        top_area = pygame.Surface((400, 240))
        top_area.fill((255, 255, 255))

        slip_files = self.get_slip_files()
        y_offset = 10
        for slip in slip_files:
            label = self.font.render(slip, True, (0, 0, 0))
            top_area.blit(label, (10, y_offset))
            y_offset += 20

        self.screen.blit(top_area, (0, 0))
        pygame.draw.line(self.screen, (0, 0, 0), (0, 240), (400, 240), 2)

        # Bottom screen: if user selected a slip, show "Edit" or "Convert"
        self.screen.blit(self.bottom_screen, (0, 242))
        if self.selected_slip:
            # Show two rectangles for Edit and Convert
            edit_rect = pygame.Rect(50, 242 + 80, 100, 40)
            conv_rect = pygame.Rect(250, 242 + 80, 100, 40)
            pygame.draw.rect(self.screen, (180, 180, 180), edit_rect)
            pygame.draw.rect(self.screen, (180, 180, 180), conv_rect)

            edit_label = self.font.render("Edit", True, (0, 0, 0))
            elx = edit_rect.centerx - edit_label.get_width() // 2
            ely = edit_rect.centery - edit_label.get_height() // 2
            self.screen.blit(edit_label, (elx, ely))

            conv_label = self.font.render("Convert", True, (0, 0, 0))
            clx = conv_rect.centerx - conv_label.get_width() // 2
            cly = conv_rect.centery - conv_label.get_height() // 2
            self.screen.blit(conv_label, (clx, cly))

    def handle_browse_keys(self, event):
        """Handle key presses in the browse section (none for now)."""
        pass

    def handle_browse_mouse_down(self, pos):
        """
        If user clicks on a slip file in the top screen, select it.
        If user clicks 'Edit' or 'Convert' on bottom screen, do the action.
        """
        if pos[1] <= 240:
            # top screen: check if user clicked on a slip file label
            slip_files = self.get_slip_files()
            y_offset = 10
            for slip in slip_files:
                label_rect = pygame.Rect(10, y_offset, 380, 20)
                if label_rect.collidepoint(pos):
                    self.selected_slip = slip
                    logging.info(f"Selected slip: {slip}")
                    break
                y_offset += 20
        else:
            # bottom screen: check if user clicked Edit or Convert
            if self.selected_slip:
                edit_rect = pygame.Rect(50, 242 + 80, 100, 40)
                conv_rect = pygame.Rect(250, 242 + 80, 100, 40)
                if edit_rect.collidepoint(pos):
                    logging.info(f"Editing slip: {self.selected_slip}")
                    self.load_slipnote(os.path.join(self.slipnote_folder, self.selected_slip))
                    self.state = "create"
                elif conv_rect.collidepoint(pos):
                    logging.info(f"Converting slip to MP4/GIF: {self.selected_slip}")
                    self.convert_slipnote(self.selected_slip)

    def get_slip_files(self):
        """Return a list of .slip files in the slipnotes folder."""
        files = []
        for f in os.listdir(self.slipnote_folder):
            if f.lower().endswith(".slip"):
                files.append(f)
        return files

    def load_slipnote(self, file_path):
        """
        Load frames from a .slip file (our simple pickle format).
        Replace current frames with loaded data.
        """
        import pickle
        try:
            with open(file_path, "rb") as f:
                slip_info = pickle.load(f)
            self.frames = []
            for frame_rgba in slip_info["frames_rgba"]:
                frame_surf = pygame.image.fromstring(frame_rgba, (slip_info["width"], slip_info["height"]), "RGBA")
                self.frames.append(frame_surf)
            self.current_frame = 0
            self.top_screen = self.frames[self.current_frame]
            logging.info(f"Loaded slipnote from {file_path}")
        except Exception as e:
            logging.error(f"Failed to load slipnote: {e}")

    def convert_slipnote(self, slip_file):
        """
        Placeholder for converting .slip to MP4 or GIF.
        Here, we just log success. In a real app, you'd use imageio/moviepy.
        """
        base_name = os.path.splitext(slip_file)[0]
        # e.g. slip_file = "my_slip.slip", base_name = "my_slip"
        # Suppose we export "my_slip.mp4" and "my_slip.gif"
        logging.info(f"Converted {slip_file} -> {base_name}.mp4, {base_name}.gif")

    # -------------------------------------------------------------------------
    # FPS & Microphone
    # -------------------------------------------------------------------------
    def select_fps(self):
        """Open a dialog to allow the user to select FPS (between 1 and 30)."""
        root = tk.Tk()
        root.withdraw()
        new_fps = simpledialog.askinteger("Select FPS", "Enter FPS (1-30):",
                                          minvalue=1, maxvalue=30, initialvalue=self.fps)
        root.destroy()
        if new_fps is not None:
            self.fps = new_fps
            logging.info("FPS set to %d", self.fps)
        else:
            logging.info("FPS selection cancelled; current FPS remains %d", self.fps)

    def select_microphone(self):
        """List available microphone devices and allow the user to select one."""
        if not PYAUDIO_AVAILABLE:
            logging.error("PyAudio not available. Cannot select microphone.")
            return

        import pyaudio
        p = pyaudio.PyAudio()
        device_list = []
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                device_list.append((i, info.get("name", "Unknown")))
        p.terminate()

        if not device_list:
            logging.error("No input devices found.")
            return

        logging.info("Available microphone devices:")
        for dev in device_list:
            logging.info("Device %d: %s", dev[0], dev[1])

        root = tk.Tk()
        root.withdraw()
        mic_index = simpledialog.askinteger("Select Microphone",
                                            "Enter microphone device index:",
                                            minvalue=0,
                                            maxvalue=max(d[0] for d in device_list),
                                            initialvalue=self.selected_device)
        root.destroy()

        if mic_index is not None:
            self.selected_device = mic_index
            self.use_virtual_mic = False
            logging.info("Selected microphone device: %d", mic_index)
        else:
            logging.info("No microphone selected; defaulting to VirtualMicrophone.")
            self.use_virtual_mic = True

    # -------------------------------------------------------------------------
    # AUDIO RECORDING
    # -------------------------------------------------------------------------
    def toggle_recording(self):
        """Start or stop recording audio."""
        if not self.is_recording:
            logging.info("Recording started (8-bit, mono).")
            self.is_recording = True
            self.audio_thread = threading.Thread(target=self.record_audio)
            self.audio_thread.start()
        else:
            self.is_recording = False
            logging.info("Recording stopped.")

    def record_audio(self):
        """Record audio until self.is_recording is False."""
        chunk = 1024
        rate = 44100
        channels = 1  # mono

        frames = []

        if PYAUDIO_AVAILABLE and not self.use_virtual_mic:
            import pyaudio
            p = pyaudio.PyAudio()
            try:
                stream = p.open(format=pyaudio.paInt8,
                                channels=channels,
                                rate=rate,
                                input=True,
                                frames_per_buffer=chunk,
                                input_device_index=self.selected_device)
                while self.is_recording:
                    data = stream.read(chunk)
                    frames.append(data)
                stream.stop_stream()
                stream.close()
                p.terminate()
            except Exception as e:
                logging.error("Error using PyAudio: %s", e)
                logging.info("Falling back to VirtualMicrophone.")
                self.use_virtual_mic = True
                p.terminate()

        if self.use_virtual_mic:
            logging.info("Using VirtualMicrophone for audio data...")
            virtual_mic = VirtualMicrophone(chunk=chunk, rate=rate)
            while self.is_recording:
                data = virtual_mic.read(chunk)
                frames.append(data)
                time.sleep(0.01)

        wf = wave.open(self.audio_file, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(1)  # 1 byte = 8 bits
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        logging.info("Audio saved to %s", self.audio_file)

    def play_recorded_audio(self):
        """Play the recorded audio file."""
        try:
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.play()
            logging.info("Playing recorded audio from %s", self.audio_file)
        except pygame.error as e:
            logging.error("Could not play recorded audio: %s", e)

    # -------------------------------------------------------------------------
    # AUDIO UPLOAD / PLAY
    # -------------------------------------------------------------------------
    def load_audio(self):
        """Open a file dialog to select a WAV or MP3 file and load it."""
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav *.mp3")])
        root.destroy()
        if file_path:
            try:
                pygame.mixer.music.load(file_path)
                self.loaded_audio_path = file_path
                logging.info("Audio file loaded: %s", file_path)
            except pygame.error as e:
                logging.error("Could not load the audio file: %s", e)
        else:
            logging.info("No file selected.")

    def play_loaded_audio(self):
        """Play the loaded external audio file."""
        if self.loaded_audio_path:
            pygame.mixer.music.play()
            logging.info("Playing loaded audio: %s", self.loaded_audio_path)
        else:
            logging.info("No audio file loaded. Press 'U' to load one.")


if __name__ == "__main__":
    SlipnoteStudio()
