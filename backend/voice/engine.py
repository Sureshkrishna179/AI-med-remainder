"""
backend/voice/engine.py — Voice Alerts Module for AI Medicine Reminder

Synthesizes voice notifications (using pyttsx3 offline text-to-speech) and checks
microphone input for patient confirmation (using speech_recognition).
Operates a background thread monitoring due medication times.
"""

import time
import threading
from datetime import datetime
import pyttsx3
import speech_recognition as sr

from backend.db.connection import execute_query


class VoiceEngine:
    """Manages text-to-speech synthesis and voice response confirmation."""

    def __init__(self):
        self._init_tts()
        self.recognizer = sr.Recognizer()
        self._triggered_this_minute = set()  # Tracks alarms fired in the current minute
        self._running = False

    def _init_tts(self):
        """Configure TTS engine with patient-friendly speech speed and voice options."""
        try:
            self.tts_engine = pyttsx3.init()
            # Slow down rate from default ~200 WPM to 140 WPM for clear comprehension
            self.tts_engine.setProperty("rate", 140)
            self.tts_engine.setProperty("volume", 1.0)
            
            # Select a clear English voice if available
            voices = self.tts_engine.getProperty("voices")
            for voice in voices:
                if "english" in voice.name.lower() or "zira" in voice.name.lower():
                    self.tts_engine.setProperty("voice", voice.id)
                    break
        except Exception as e:
            print(f"⚠️ Warning initializing TTS engine: {e}")

    def speak(self, text):
        """Synthesize text speech. Re-initializes per-call to prevent thread issues on Windows."""
        print(f"🔊 Speaking: {text}")
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 140)
            engine.setProperty("volume", 1.0)
            voices = engine.getProperty("voices")
            for voice in voices:
                if "english" in voice.name.lower() or "zira" in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"❌ Text-To-Speech Synthesis Error: {e}")

    def listen_for_confirmation(self, timeout=10):
        """Listen via mic for patient confirmation. Returns text or None if unsuccessful."""
        try:
            with sr.Microphone() as source:
                print("🎤 Calibration: Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print(f"🎤 Listening (max timeout {timeout}s)...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=8)

            # Try online Google service first, fallback to offline Sphinx engine
            try:
                text = self.recognizer.recognize_google(audio)
                print(f"🎤 Speech recognized (Google): '{text}'")
                return text.lower()
            except sr.UnknownValueError:
                print("🎤 Speech heard but not understood.")
                return None
            except sr.RequestError:
                # Online API failed or no internet connection; attempt Sphinx offline fallback
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                    print(f"🎤 Speech recognized (Sphinx offline): '{text}'")
                    return text.lower()
                except Exception:
                    print("🎤 Offline speech recognition engine failure.")
                    return None

        except sr.WaitTimeoutError:
            print("🎤 No speech detected within the window.")
            return None
        except OSError as e:
            print(f"❌ Microphone input hardware error: {e}")
            return None
        except Exception as e:
            print(f"❌ Speech-To-Text processing error: {e}")
            return None

    def _get_due_schedules(self, current_time_str):
        """Query schedules matching the specified time (HH:MM)."""
        parts = current_time_str.split(":")
        if len(parts) != 2:
            return []
        
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return []

        # Compare using HOUR and MINUTE values for maximum safety and cleanliness
        query = """
            SELECT * FROM schedules 
            WHERE HOUR(alarm_time) = %s 
              AND MINUTE(alarm_time) = %s 
              AND is_active = TRUE
        """
        results = execute_query(query, (hour, minute), fetch=True)
        return results or []

    def _log_adherence(self, schedule_id, status):
        """Record a log entry for a triggered medication alert."""
        query = "INSERT INTO adherence_logs (schedule_id, triggered_at, status) VALUES (%s, %s, %s)"
        result = execute_query(query, (schedule_id, datetime.now(), status))
        if result is not None:
            print(f"📝 Logged: Schedule #{schedule_id} status marked as '{status}'")
        else:
            print(f"❌ Error writing adherence log for Schedule #{schedule_id}")

    def run_scheduler(self):
        """Continuous scheduler loop checking for due alarms every 30 seconds."""
        self._running = True
        print("\n" + "=" * 60)
        print("🧠 AI Voice Scheduler: Background loop running...")
        print("=" * 60 + "\n")

        while self._running:
            try:
                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                current_minute_key = now.strftime("%Y-%m-%d %H:%M")

                due_schedules = self._get_due_schedules(current_time_str)

                for schedule in due_schedules:
                    alarm_key = f"{schedule['schedule_id']}_{current_minute_key}"

                    # Prevent duplicate triggering within the same minute
                    if alarm_key in self._triggered_this_minute:
                        continue

                    self._triggered_this_minute.add(alarm_key)

                    patient = schedule["patient_name"]
                    medicine = schedule["medicine_name"]
                    dosage = schedule["dosage"]
                    time_str = str(schedule["alarm_time"])

                    reminder_phrase = (
                        f"Attention! Hello {patient}. "
                        f"It is time to take {dosage} of {medicine}. "
                        f"This was scheduled for {time_str}. "
                        f"Please confirm by saying taken or done."
                    )
                    self.speak(reminder_phrase)

                    print(f"\n⏳ Awaiting verbal response from {patient}...")
                    response = self.listen_for_confirmation(timeout=10)

                    # Log response status based on keywords
                    if response and any(word in response for word in ["taken", "done", "yes", "took"]):
                        self._log_adherence(schedule["schedule_id"], "Taken")
                        self.speak(f"Thank you {patient}. Your dose of {medicine} has been recorded as taken.")
                    else:
                        self._log_adherence(schedule["schedule_id"], "Missed")
                        self.speak(f"Alert. No confirmation received for {medicine}. Logging as missed.")

                # Cleanup previous minute tracking flags
                expired_keys = [
                    k for k in self._triggered_this_minute
                    if current_minute_key not in k
                ]
                for k in expired_keys:
                    self._triggered_this_minute.discard(k)

            except Exception as e:
                print(f"❌ Voice Engine Scheduler Error: {e}")

            time.sleep(30)

    def stop_scheduler(self):
        """Terminate the scheduler check loop."""
        self._running = False
        print("🛑 AI Voice Scheduler: Background loop stopped.")

    def start_scheduler_thread(self):
        """Spawn the scheduler loop inside a daemon thread."""
        thread = threading.Thread(target=self.run_scheduler, daemon=True)
        thread.start()
        return thread


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Voice Engine Module Test")
    print("=" * 50)

    engine = VoiceEngine()
    engine.speak("Voice system testing.")
    
    print("\nStarting scheduler... Press Ctrl+C to terminate.")
    try:
        engine.run_scheduler()
    except KeyboardInterrupt:
        engine.stop_scheduler()
