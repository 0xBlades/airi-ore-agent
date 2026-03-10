"""
Airi Voice Command Module
Listens for voice input, matches keywords, and executes OS commands.
Plays an MP3 response upon successful execution.
"""

import os
import threading
import pygame
import speech_recognition as sr
from pathlib import Path


class VoiceCommandExecutor:
    def __init__(self, callback=None):
        """
        callback: function(status_text, command_recognized)
        """
        self.callback = callback
        self.recognizer = sr.Recognizer()
        self.is_listening = False
        
        # Initialize audio player
        pygame.mixer.init()
        self.audio_response_path = Path(__file__).parent.parent / "assets" / "response.mp3"
        
        # Ensure the assets directory exists
        self.audio_response_path.parent.mkdir(parents=True, exist_ok=True)

    def play_response_audio(self):
        """Play the configured MP3 audio file."""
        if self.audio_response_path.exists():
            try:
                pygame.mixer.music.load(str(self.audio_response_path))
                pygame.mixer.music.play()
            except Exception as e:
                print(f"[VoiceCmd] Error playing audio: {e}")
        else:
            print(f"[VoiceCmd] Audio file not found at {self.audio_response_path}")

    def trigger_listen(self):
        """Start listening in a background thread."""
        if self.is_listening:
            return
            
        self.is_listening = True
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        """Worker thread for recording and recognizing speech."""
        self._emit_status("Sedang mendengarkan...", True)
        
        with sr.Microphone() as source:
            # Adjust for ambient noise briefly
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                # Listen for up to 5 seconds
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                self._emit_status("Memproses suara...", True)
                
                # Recognize speech using Google Web Speech API (Indonesian)
                text = self.recognizer.recognize_google(audio, language="id-ID")
                print(f"[VoiceCmd] Dikenali: {text}")
                
                # Execute command
                self._execute_action(text.lower())
                
            except sr.WaitTimeoutError:
                self._emit_status("Tidak ada suara tedeteksi", False)
            except sr.UnknownValueError:
                self._emit_status("Suara tidak jelas / tidak dipahami", False)
            except sr.RequestError as e:
                self._emit_status(f"Error jaringan: {e}", False)
            except Exception as e:
                self._emit_status(f"Error sistem: {e}", False)
            finally:
                self.is_listening = False

    def _execute_action(self, text: str):
        """Keyword matching and execution."""
        executed = False
        
        if "buka youtube" in text:
            os.system("start https://youtube.com")
            executed = True
        elif "buka google" in text:
            os.system("start https://google.com")
            executed = True
        elif "buka browser" in text:
            os.system("start https://google.com")
            executed = True
        elif "buka notepad" in text:
            os.system("start notepad")
            executed = True
        elif "buka kalkulator" in text:
            os.system("start calc")
            executed = True
        elif "buka file explorer" in text or "buka folder" in text:
            os.system("start explorer")
            executed = True
        elif "buka setting" in text or "buka pengaturan" in text:
            os.system("start ms-settings:")
            executed = True
            
        if executed:
            self._emit_status(f"Menjalankan: '{text}'", False, command=text)
            self.play_response_audio()
        else:
            self._emit_status(f"Perintah belum disupport: '{text}'", False, command=text)

    def _emit_status(self, msg: str, is_active: bool, command: str = None):
        """Send status back to the UI."""
        if self.callback:
            try:
                self.callback({
                    "status": msg,
                    "is_active": is_active,
                    "command": command
                })
            except Exception:
                pass
