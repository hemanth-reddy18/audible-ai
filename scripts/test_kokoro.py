import time
import os
import soundfile as sf
from kokoro_onnx import Kokoro

model_path = os.path.abspath("models/kokoro/kokoro-v0_19.onnx")
voices_path = os.path.abspath("models/kokoro/voices.bin")

print(f"Loading Kokoro model from {model_path}...")
t0 = time.time()
kokoro = Kokoro(model_path, voices_path)
print(f"Loaded in {time.time()-t0:.2f}s")

text = "Hello! Welcome to FreshMart Supermarket. How may I help you today, sir?"
print(f"Synthesizing: '{text}'")
print("Available voices:", kokoro.get_voices())
first_voice = kokoro.get_voices()[0]
print(f"Using voice: {first_voice}")
t1 = time.time()
samples, sample_rate = kokoro.create(text, voice=first_voice, speed=1.0, lang="en-us")
t2 = time.time()
duration = len(samples) / sample_rate
print(f"Synthesized in {t2-t1:.2f}s | Audio duration: {duration:.2f}s | Sample rate: {sample_rate}Hz | RTF: {(t2-t1)/duration:.3f}")

output_wav = os.path.abspath("models/kokoro/test_synthesis.wav")
sf.write(output_wav, samples, sample_rate)
print(f"Saved to {output_wav} ({os.path.getsize(output_wav)} bytes)")
