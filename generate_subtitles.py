#!/usr/bin/env python3

import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import sys
import os
import json
from vosk import Model, KaldiRecognizer, SetLogLevel
from googletrans import Translator

SAMPLE_RATE = 16000

SetLogLevel(-1)

model_path = os.path.join(
    os.path.dirname(__file__), "vosk-model-small-en-us-0.15", "vosk-model-small-en-us-0.15"
)
print(model_path)
model = Model(model_path)
rec = KaldiRecognizer(model, SAMPLE_RATE)
rec.SetWords(True)

translator = Translator()

# Database setup
def setup_database():
    conn = sqlite3.connect('subtitles.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subtitles (
            id INTEGER PRIMARY KEY,
            audio_file TEXT,
            generated_subtitles TEXT,
            translated_subtitles TEXT
        )
    ''')
    conn.commit()
    conn.close()

def select_file():
    global audio_file
    audio_file = filedialog.askopenfilename(title="Select Audio File", filetypes=[("Audio Files", "*.wav;*.mp3")])
    if audio_file:
        messagebox.showinfo("File Selected", f"Selected file: {audio_file}")

def format_timestamp(seconds):
    millis = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

# Language options for subtitles
language_options = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
}

# GUI setup
root = tk.Tk()
root.title("Subtitle Generator")
root.geometry("400x200")

# Move the initialization of language_var here
language_var = tk.StringVar()

language_label = tk.Label(root, text="Select Subtitle Language:")
language_label.pack(pady=5)

language_menu = tk.OptionMenu(root, language_var, *language_options.keys())
language_menu.pack(pady=5)

language_var.set("English")  # Set default value after root is created

def generate_subtitles():
    selected_language = language_options[language_var.get()]

    # Check if the file exists
    if not os.path.isfile(audio_file):
        messagebox.showerror("Error", f"The file '{audio_file}' does not exist.")
        return

    # Determine output file name
    output_file = os.path.splitext(audio_file)[0] + "_subtitles.srt"
    translated_output_file = os.path.splitext(audio_file)[0] + "_subtitles_translated.srt"

    with subprocess.Popen(["ffmpeg", "-loglevel", "quiet", "-i",
                           audio_file,
                           "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "s16le", "-"],
                          stdout=subprocess.PIPE).stdout as stream:

        subtitles = ""
        srt_format = ""
        counter = 1
        while True:
            data = stream.read(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if 'result' in result and result['result']:
                    # Format as SRT
                    for word in result['result']:
                        start_time = format_timestamp(word['start'])
                        end_time = format_timestamp(word['end'])
                        srt_format += f"{counter}\n{start_time} --> {end_time}\n{word['word']}\n\n"
                        counter += 1
            else:
                partial = json.loads(rec.PartialResult())

        final_result = json.loads(rec.FinalResult())

    # Check if subtitles are not empty before translation
    if not srt_format.strip():
        messagebox.showerror("Error", "No subtitles generated. Please check the audio file.")
        return
    if srt_format.strip():

        try:
            translated_subtitles = translator.translate(srt_format, dest='es').text  # Change 'es' to desired language code
        except Exception as e:
            messagebox.showerror("Translation Error", str(e))
            translated_subtitles = ""

        # Save to database
        conn = sqlite3.connect('subtitles.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subtitles (audio_file, generated_subtitles, translated_subtitles)
            VALUES (?, ?, ?)
        ''', (audio_file, srt_format, translated_subtitles))
        conn.commit()
        conn.close()

        with open(output_file, "w") as file:
            file.write(srt_format)

        with open(translated_output_file, "w") as file:
            file.write(translated_subtitles)

        messagebox.showinfo("Success", f"Subtitles have been generated and saved to '{output_file}'.")
        messagebox.showinfo("Success", f"Translated subtitles have been saved to '{translated_output_file}'.")

# Setup database
setup_database()

select_button = tk.Button(root, text="Select Audio File", command=select_file)
select_button.pack(pady=20)

generate_button = tk.Button(root, text="Generate Subtitles", command=generate_subtitles)
generate_button.pack(pady=20)

root.mainloop()
