# -*- coding: utf-8 -*-

#
# Copyright (C) 2026 Amlogic, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
from collections import deque
import os
import queue
import re
import subprocess
import threading

from transformers import WhisperProcessor
import librosa
import numpy as np

try:
    from amlnnlite.api import AMLNNLite as AMLNN
except ImportError:
    from amlnn.api import AMLNN

SAMPLE_RATE = 16000
TARGET_SAMPLES = 30 * SAMPLE_RATE
OVERLAP_SECONDS = 2
DEFAULT_LANGUAGE = "auto"
DEFAULT_MIC_DEVICE = "hw:0,3"
DEFAULT_CAPTURE_RATE = 48000
DEFAULT_CAPTURE_CHANNELS = 6


def get_audio_segments(audio_path, sample_rate, target_samples, overlap_samples):
    waveform, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
    waveform = np.asarray(waveform, dtype=np.float32)

    if waveform.size == 0:
        raise ValueError(f"Audio file contains no samples: {audio_path}")

    step_samples = target_samples - overlap_samples
    if step_samples <= 0:
        raise ValueError("Overlap must be shorter than the model input length")

    segments = []
    start = 0

    while True:
        segment = waveform[start:start + target_samples]
        segments.append(segment)

        if start + target_samples >= waveform.size:
            break

        start += step_samples

    return segments


def resample_audio(waveform, source_rate, target_rate):
    waveform = np.asarray(waveform, dtype=np.float32)
    if source_rate == target_rate:
        return waveform

    return np.asarray(
        librosa.resample(
            waveform,
            orig_sr=source_rate,
            target_sr=target_rate
        ),
        dtype=np.float32
    )


def preprocess_audio(waveform, processor, input_shape, s, zp, tensor_type):
    input_features = processor(
        waveform,
        sampling_rate=SAMPLE_RATE,
        return_tensors="np"
    ).input_features
    input_features = np.asarray(input_features, dtype=np.float32)

    expected_elements = int(np.prod(input_shape))
    if input_features.size != expected_elements:
        raise ValueError(
            f"input_features contains {input_features.size} elements, "
            f"expected {expected_elements} for input shape {input_shape}"
        )

    input_features = input_features.reshape(input_shape)

    if tensor_type == 0:  # FP32 & FP16
        input_tensor = input_features.astype(np.float32)
    elif tensor_type in (2, 3, 4):
        raw_val = np.round(input_features / s + zp)

        if tensor_type == 2:    # Int8
            input_tensor = np.clip(raw_val, -128, 127).astype(np.int8)
        elif tensor_type == 3:  # Uint8
            input_tensor = np.clip(raw_val, 0, 255).astype(np.uint8)
        else:                   # Int16
            input_tensor = np.clip(raw_val, -32768, 32767).astype(np.int16)
    else:
        raise ValueError(f"Does not support encoder input tensor type: {tensor_type}")

    return np.ascontiguousarray(input_tensor)


def prepare_encoder_hidden_states(encoder_output, input_shape, s, zp, tensor_type):
    encoder_output = np.asarray(encoder_output, dtype=np.float32)

    expected_elements = int(np.prod(input_shape))
    if encoder_output.size != expected_elements:
        raise ValueError(
            f"Encoder output contains {encoder_output.size} elements, "
            f"decoder encoder_hidden_states expects {expected_elements}"
        )

    encoder_output = encoder_output.reshape(input_shape)

    if tensor_type == 0:  # FP32 & FP16
        input_tensor = encoder_output.astype(np.float32)
    elif tensor_type in (2, 3, 4):
        raw_val = np.round(encoder_output / s + zp)

        if tensor_type == 2:    # Int8
            input_tensor = np.clip(raw_val, -128, 127).astype(np.int8)
        elif tensor_type == 3:  # Uint8
            input_tensor = np.clip(raw_val, 0, 255).astype(np.uint8)
        else:                   # Int16
            input_tensor = np.clip(raw_val, -32768, 32767).astype(np.int16)
    else:
        raise ValueError(
            f"Does not support decoder encoder_hidden_states tensor type: {tensor_type}"
        )

    return np.ascontiguousarray(input_tensor)


def get_decoder_tokens(processor, language):
    tokenizer = processor.tokenizer
    tokenizer.set_prefix_tokens(
        language=language,
        task="transcribe",
        predict_timestamps=False
    )

    decoder_tokens = list(tokenizer.prefix_tokens)
    if not decoder_tokens:
        raise ValueError("Whisper tokenizer returned no decoder prefix tokens")

    if tokenizer.eos_token_id is None:
        raise ValueError("Whisper tokenizer does not define an end token")

    pad_token_id = tokenizer.pad_token_id
    if pad_token_id is None:
        pad_token_id = tokenizer.eos_token_id

    return decoder_tokens, int(tokenizer.eos_token_id), int(pad_token_id)


def detect_language(
    decoder_amlnn,
    decoder_ids_shape,
    decoder_hidden_states,
    decoder_output_shape,
    processor
):
    tokenizer = processor.tokenizer
    decoder_length = int(np.prod(decoder_ids_shape))
    vocab_size = int(decoder_output_shape[-1])
    output_steps = int(np.prod(decoder_output_shape)) // vocab_size

    if output_steps != decoder_length:
        raise ValueError(
            f"Decoder output has {output_steps} positions, "
            f"but decoder input length is {decoder_length}"
        )

    start_token = "<|startoftranscript|>"
    start_token_id = int(tokenizer.convert_tokens_to_ids(start_token))
    if tokenizer.convert_ids_to_tokens(start_token_id) != start_token:
        raise ValueError("Whisper tokenizer does not define a start-of-transcript token")

    if tokenizer.eos_token_id is None:
        raise ValueError("Whisper tokenizer does not define an end token")

    pad_token_id = tokenizer.pad_token_id
    if pad_token_id is None:
        pad_token_id = tokenizer.eos_token_id

    # Whisper language tokens use the form <|en|>, <|zh|>, <|yue|>, etc.
    # Discover them from this tokenizer instead of assuming fixed token IDs.
    language_tokens = []
    for token, token_id in tokenizer.get_vocab().items():
        if re.fullmatch(r"<\|[a-z]{2,3}\|>", token) and int(token_id) < vocab_size:
            language_tokens.append((token, int(token_id)))

    if not language_tokens:
        raise ValueError("No language tokens were found in the Whisper tokenizer")

    decoder_input_ids = np.full(decoder_length, pad_token_id, dtype=np.int64)
    decoder_input_ids[0] = start_token_id
    decoder_input_ids = decoder_input_ids.reshape(decoder_ids_shape)

    outputs = decoder_amlnn.inference(
        inputs=[decoder_input_ids, decoder_hidden_states]
    )
    if outputs is None or len(outputs) == 0:
        raise ValueError("Decoder language detection returned no outputs")

    logits = np.asarray(outputs[0], dtype=np.float32)
    expected_elements = int(np.prod(decoder_output_shape))
    if logits.size != expected_elements:
        raise ValueError(
            f"Decoder output contains {logits.size} elements, "
            f"expected {expected_elements}"
        )

    logits = logits.reshape(output_steps, vocab_size)
    language_logits = np.asarray(
        [logits[0, token_id] for _, token_id in language_tokens],
        dtype=np.float64
    )
    best_index = int(np.argmax(language_logits))
    best_token = language_tokens[best_index][0]

    # Report probability normalized over language tokens, matching Whisper's
    # language-detection semantics.
    shifted_logits = language_logits - np.max(language_logits)
    language_probabilities = np.exp(shifted_logits)
    language_probabilities /= np.sum(language_probabilities)

    language = best_token[2:-2]
    confidence = float(language_probabilities[best_index])
    return language, confidence


def run_decoder_loop(
    decoder_amlnn,
    decoder_ids_shape,
    decoder_hidden_states,
    decoder_output_shape,
    processor,
    language
):
    decoder_length = int(np.prod(decoder_ids_shape))
    vocab_size = int(decoder_output_shape[-1])
    output_steps = int(np.prod(decoder_output_shape)) // vocab_size

    if output_steps != decoder_length:
        raise ValueError(
            f"Decoder output has {output_steps} positions, "
            f"but decoder input length is {decoder_length}"
        )

    decoder_tokens, token_eot, pad_token_id = get_decoder_tokens(processor, language)

    if len(decoder_tokens) >= decoder_length:
        raise ValueError(
            f"Decoder prefix has {len(decoder_tokens)} tokens, "
            f"but decoder input length is {decoder_length}"
        )

    while len(decoder_tokens) < decoder_length:
        decoder_input_ids = np.full(decoder_length, pad_token_id, dtype=np.int64)
        decoder_input_ids[:len(decoder_tokens)] = decoder_tokens
        decoder_input_ids = decoder_input_ids.reshape(decoder_ids_shape)

        outputs = decoder_amlnn.inference(
            inputs=[decoder_input_ids, decoder_hidden_states]
        )

        if outputs is None or len(outputs) == 0:
            raise ValueError("Decoder inference returned no outputs")

        logits = np.asarray(outputs[0], dtype=np.float32)

        expected_elements = int(np.prod(decoder_output_shape))
        if logits.size != expected_elements:
            raise ValueError(
                f"Decoder output contains {logits.size} elements, "
                f"expected {expected_elements}"
            )

        logits = logits.reshape(output_steps, vocab_size)
        next_token = int(np.argmax(logits[len(decoder_tokens) - 1]))
        decoder_tokens.append(next_token)

        if next_token == token_eot:
            break

    return processor.decode(
        decoder_tokens,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    ).strip()


def transcribe_waveform(waveform, runtime, language):
    input_features = preprocess_audio(
        waveform,
        runtime["processor"],
        runtime["encoder_input_shape"],
        runtime["encoder_s"],
        runtime["encoder_zp"],
        runtime["encoder_type"]
    )

    encoder_outputs = runtime["encoder"].inference(inputs=[input_features])
    if encoder_outputs is None or len(encoder_outputs) == 0:
        raise ValueError("Encoder inference returned no outputs")

    encoder_output = np.asarray(encoder_outputs[0], dtype=np.float32)
    expected_encoder_elements = int(np.prod(runtime["encoder_output_shape"]))
    if encoder_output.size != expected_encoder_elements:
        raise ValueError(
            f"Encoder output contains {encoder_output.size} elements, "
            f"expected {expected_encoder_elements}"
        )

    decoder_hidden_states = prepare_encoder_hidden_states(
        encoder_output,
        runtime["decoder_hidden_shape"],
        runtime["decoder_hidden_s"],
        runtime["decoder_hidden_zp"],
        runtime["decoder_hidden_type"]
    )

    detected_language = language
    confidence = None
    if detected_language == "auto":
        detected_language, confidence = detect_language(
            runtime["decoder"],
            runtime["decoder_ids_shape"],
            decoder_hidden_states,
            runtime["decoder_output_shape"],
            runtime["processor"]
        )

    transcription = run_decoder_loop(
        runtime["decoder"],
        runtime["decoder_ids_shape"],
        decoder_hidden_states,
        runtime["decoder_output_shape"],
        runtime["processor"],
        detected_language
    )
    runtime["inference_count"] += 1
    return transcription, detected_language, confidence


def normalize_word(word):
    return "".join(character.lower() for character in word if character.isalnum() or character == "'")


def merge_transcriptions(transcriptions):
    combined = ""

    for transcription in transcriptions:
        transcription = transcription.strip()
        if not transcription:
            continue

        if not combined:
            combined = transcription
            continue

        previous_words = combined.split()
        current_words = transcription.split()
        max_overlap = min(len(previous_words), len(current_words))
        matched_words = 0

        for count in range(max_overlap, 0, -1):
            previous_suffix = [normalize_word(word) for word in previous_words[-count:]]
            current_prefix = [normalize_word(word) for word in current_words[:count]]

            if previous_suffix == current_prefix and all(previous_suffix):
                matched_words = count
                break

        if matched_words > 0:
            combined = " ".join(previous_words + current_words[matched_words:])
            continue

        previous_last = normalize_word(previous_words[-1])
        current_first = normalize_word(current_words[0])

        if len(previous_last) >= 3 and current_first.startswith(previous_last):
            combined = " ".join(previous_words[:-1] + current_words)
        elif len(current_first) >= 3 and previous_last.startswith(current_first):
            combined = " ".join(previous_words + current_words[1:])
        else:
            combined = combined.rstrip() + " " + transcription.lstrip()

    return combined.strip()


class AlsaRecorder:
    """Continuously read interleaved signed 16-bit PCM from arecord."""

    _END = object()

    def __init__(self, device, sample_rate, channels, chunk_ms, mic_channel):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_frames = max(1, sample_rate * chunk_ms // 1000)
        self.chunk_bytes = self.chunk_frames * channels * 2
        self.mic_channel = mic_channel
        self.process = None
        self.reader_thread = None
        self.chunks = queue.Queue()

    def start(self):
        command = [
            "arecord",
            "-q",
            "-D", self.device,
            "-t", "raw",
            "-r", str(self.sample_rate),
            "-f", "S16_LE",
            "-c", str(self.channels),
            "-"
        ]
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                bufsize=0
            )
        except FileNotFoundError as error:
            raise RuntimeError("arecord was not found; install alsa-utils first") from error

        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()

    def _read_loop(self):
        pending = bytearray()
        try:
            while True:
                data = self.process.stdout.read(self.chunk_bytes - len(pending))
                if not data:
                    break
                pending.extend(data)
                if len(pending) == self.chunk_bytes:
                    self.chunks.put(bytes(pending))
                    pending.clear()
        finally:
            self.chunks.put(self._END)

    def read(self):
        data = self.chunks.get()
        if data is self._END:
            return_code = self.process.poll()
            if return_code is None:
                return_code = self.process.wait()
            raise RuntimeError(f"arecord stopped unexpectedly (exit code {return_code})")

        samples = np.frombuffer(data, dtype="<i2").reshape(-1, self.channels)
        if self.mic_channel == "mix":
            waveform = samples.astype(np.float32).mean(axis=1)
        else:
            waveform = samples[:, self.mic_channel].astype(np.float32)
        return waveform / 32768.0

    def stop(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.reader_thread is not None:
            self.reader_thread.join(timeout=2)


def parse_mic_channel(value, channels):
    value = value.strip().lower()
    if value == "mix":
        return value
    try:
        channel = int(value)
    except ValueError as error:
        raise ValueError("--mic-channel must be an integer or 'mix'") from error
    if channel < 0 or channel >= channels:
        raise ValueError(
            f"--mic-channel must be between 0 and {channels - 1}, or 'mix'"
        )
    return channel


def waveform_rms(waveform):
    waveform = np.asarray(waveform, dtype=np.float32)
    if waveform.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(waveform, dtype=np.float32))))


def run_microphone(runtime, args):
    mic_channel = parse_mic_channel(args.mic_channel, args.capture_channels)
    recorder = AlsaRecorder(
        args.device,
        args.capture_rate,
        args.capture_channels,
        args.chunk_ms,
        mic_channel
    )

    calibration_chunks = max(
        1,
        int(round(args.calibration_seconds * 1000 / args.chunk_ms))
    )
    silence_chunks = max(1, int(round(args.silence_ms / args.chunk_ms)))
    pre_roll_chunks = max(0, int(round(args.pre_roll_ms / args.chunk_ms)))
    min_speech_samples = int(args.min_speech_ms * args.capture_rate / 1000)
    max_utterance_samples = int(args.max_utterance_seconds * args.capture_rate)

    pre_roll = deque(maxlen=pre_roll_chunks)
    utterance_chunks = []
    utterance_samples = 0
    utterance_voiced_samples = 0
    quiet_chunks = 0
    speech_active = False
    result_index = 0

    def recognize(chunks, voiced_samples):
        nonlocal result_index
        if not chunks or voiced_samples < min_speech_samples:
            return
        waveform = np.concatenate(chunks)
        duration = waveform.size / args.capture_rate
        waveform = resample_audio(waveform, args.capture_rate, SAMPLE_RATE)
        try:
            transcription, language, confidence = transcribe_waveform(
                waveform,
                runtime,
                args.language
            )
            result_index += 1
            language_text = language
            if confidence is not None:
                language_text += f" {confidence:.0%}"
            if transcription:
                print(
                    f"[{result_index:03d} | {duration:.1f}s | {language_text}] "
                    f"{transcription}",
                    flush=True
                )
            else:
                print(
                    f"[{result_index:03d} | {duration:.1f}s | {language_text}] "
                    "(no speech recognized)",
                    flush=True
                )
        except Exception as error:
            print(f"Recognition error: {error}", flush=True)

    print(
        f"Microphone: {args.device}, {args.capture_rate} Hz, "
        f"{args.capture_channels} channels, selected={mic_channel}"
    )
    print(
        f"Calibrating ambient noise for {args.calibration_seconds:.1f}s; "
        "please keep quiet...",
        flush=True
    )

    recorder.start()
    try:
        noise_levels = [waveform_rms(recorder.read()) for _ in range(calibration_chunks)]
        noise_rms = float(np.median(noise_levels))
        if args.energy_threshold > 0:
            energy_threshold = args.energy_threshold
        else:
            energy_threshold = max(
                args.min_energy_threshold,
                noise_rms * args.vad_ratio
            )

        print(
            f"Noise RMS={noise_rms:.5f}, speech threshold={energy_threshold:.5f}"
        )
        print("Listening... Speak normally; press Ctrl+C to stop.", flush=True)

        while True:
            chunk = recorder.read()
            rms = waveform_rms(chunk)

            if not speech_active:
                if rms >= energy_threshold:
                    speech_active = True
                    quiet_chunks = 0
                    utterance_chunks = list(pre_roll)
                    utterance_samples = sum(item.size for item in utterance_chunks)
                    utterance_chunks.append(chunk)
                    utterance_samples += chunk.size
                    utterance_voiced_samples = chunk.size
                    pre_roll.clear()
                    print("Speech detected...", flush=True)
                else:
                    pre_roll.append(chunk)
                continue

            utterance_chunks.append(chunk)
            utterance_samples += chunk.size
            if rms < energy_threshold * 0.7:
                quiet_chunks += 1
            else:
                quiet_chunks = 0
                utterance_voiced_samples += chunk.size

            reached_silence = quiet_chunks >= silence_chunks
            reached_limit = utterance_samples >= max_utterance_samples
            if reached_silence or reached_limit:
                current_utterance = utterance_chunks
                current_voiced_samples = utterance_voiced_samples
                utterance_chunks = []
                utterance_samples = 0
                utterance_voiced_samples = 0
                quiet_chunks = 0
                speech_active = False
                recognize(current_utterance, current_voiced_samples)

    except KeyboardInterrupt:
        print("\nStopping microphone...", flush=True)
        if speech_active:
            recognize(utterance_chunks, utterance_voiced_samples)
    finally:
        recorder.stop()


def main():
    parser = argparse.ArgumentParser(description="Whisper ADLA Demo")
    parser.add_argument("--enc", required=True, help="Path to encoder .adla model")
    parser.add_argument("--dec", required=True, help="Path to decoder .adla model")
    parser.add_argument("--tokenizer", required=True, help="Path to local Whisper processor directory")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--audio-file", help="Path to input audio file")
    input_group.add_argument(
        "--microphone",
        action="store_true",
        help="Continuously transcribe speech captured with arecord"
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help="Spoken language code/name, or 'auto' to detect it (default: auto)"
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_MIC_DEVICE,
        help=f"ALSA capture device (default: {DEFAULT_MIC_DEVICE})"
    )
    parser.add_argument(
        "--capture-rate",
        type=int,
        default=DEFAULT_CAPTURE_RATE,
        help=f"Microphone sample rate (default: {DEFAULT_CAPTURE_RATE})"
    )
    parser.add_argument(
        "--capture-channels",
        type=int,
        default=DEFAULT_CAPTURE_CHANNELS,
        help=f"Number of interleaved microphone channels (default: {DEFAULT_CAPTURE_CHANNELS})"
    )
    parser.add_argument(
        "--mic-channel",
        default="0",
        help="Zero-based channel to transcribe, or 'mix' to average all channels (default: 0)"
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=100,
        help="Audio capture/VAD block duration in milliseconds (default: 100)"
    )
    parser.add_argument(
        "--silence-ms",
        type=int,
        default=1000,
        help="Silence that ends an utterance in milliseconds (default: 1000)"
    )
    parser.add_argument(
        "--min-speech-ms",
        type=int,
        default=300,
        help="Discard speech segments shorter than this (default: 300)"
    )
    parser.add_argument(
        "--pre-roll-ms",
        type=int,
        default=300,
        help="Audio retained before speech is detected (default: 300)"
    )
    parser.add_argument(
        "--max-utterance-seconds",
        type=float,
        default=15.0,
        help="Force a result after this much continuous speech (default: 15)"
    )
    parser.add_argument(
        "--calibration-seconds",
        type=float,
        default=1.5,
        help="Ambient-noise calibration duration (default: 1.5)"
    )
    parser.add_argument(
        "--energy-threshold",
        type=float,
        default=0.0,
        help="Speech RMS threshold; 0 selects it automatically (default: 0)"
    )
    parser.add_argument(
        "--min-energy-threshold",
        type=float,
        default=0.003,
        help="Lower bound for the automatic RMS threshold (default: 0.003)"
    )
    parser.add_argument(
        "--vad-ratio",
        type=float,
        default=3.0,
        help="Automatic threshold multiplier over ambient RMS (default: 3.0)"
    )
    args = parser.parse_args()
    args.language = args.language.strip().lower()

    if args.audio_file and not os.path.isfile(args.audio_file):
        print(f"Audio file not found: {args.audio_file}")
        return 1
    if args.capture_rate <= 0 or args.capture_channels <= 0:
        parser.error("--capture-rate and --capture-channels must be positive")
    if args.chunk_ms <= 0 or args.silence_ms <= 0 or args.min_speech_ms <= 0:
        parser.error("VAD time values must be positive")
    if args.pre_roll_ms < 0 or args.calibration_seconds <= 0:
        parser.error("--pre-roll-ms cannot be negative and calibration must be positive")
    if not 0 < args.max_utterance_seconds <= 30:
        parser.error("--max-utterance-seconds must be greater than 0 and at most 30")
    if args.energy_threshold < 0 or args.min_energy_threshold <= 0 or args.vad_ratio <= 0:
        parser.error("VAD threshold values must be positive (or 0 for automatic threshold)")
    try:
        parse_mic_channel(args.mic_channel, args.capture_channels)
    except ValueError as error:
        parser.error(str(error))

    processor = WhisperProcessor.from_pretrained(
        args.tokenizer,
        local_files_only=True,
        clean_up_tokenization_spaces=False
    )

    encoder_amlnn = AMLNN()
    decoder_amlnn = AMLNN()

    encoder_amlnn.init_runtime(mode="native", enable_perf=True)
    encoder_amlnn.load_model(path=args.enc)
    encoder_tensor_info = encoder_amlnn.get_tensor_info()

    decoder_amlnn.init_runtime(mode="native", enable_perf=True)
    decoder_amlnn.load_model(path=args.dec)
    decoder_tensor_info = decoder_amlnn.get_tensor_info()

    print(encoder_amlnn.get_sdk_version())

    encoder_input_attr = encoder_tensor_info["inputs"][0]
    encoder_output_attr = encoder_tensor_info["outputs"][0]

    decoder_ids_attr = decoder_tensor_info["inputs"][0]
    decoder_hidden_attr = decoder_tensor_info["inputs"][1]
    decoder_output_attr = decoder_tensor_info["outputs"][0]

    encoder_input_shape = tuple(int(value) for value in encoder_input_attr["dims"])
    encoder_output_shape = tuple(int(value) for value in encoder_output_attr["dims"])
    decoder_ids_shape = tuple(int(value) for value in decoder_ids_attr["dims"])
    decoder_hidden_shape = tuple(int(value) for value in decoder_hidden_attr["dims"])
    decoder_output_shape = tuple(int(value) for value in decoder_output_attr["dims"])

    encoder_s = float(encoder_input_attr["scale"])
    encoder_zp = int(encoder_input_attr["zp"])
    encoder_type = int(encoder_input_attr["type"])

    decoder_hidden_s = float(decoder_hidden_attr["scale"])
    decoder_hidden_zp = int(decoder_hidden_attr["zp"])
    decoder_hidden_type = int(decoder_hidden_attr["type"])

    print(f"Encoder input: name={encoder_input_attr['name']}, shape={encoder_input_shape}")
    print(f"Encoder output: name={encoder_output_attr['name']}, shape={encoder_output_shape}")
    print(f"Decoder input 0: name={decoder_ids_attr['name']}, shape={decoder_ids_shape}")
    print(f"Decoder input 1: name={decoder_hidden_attr['name']}, shape={decoder_hidden_shape}")
    print(f"Decoder output: name={decoder_output_attr['name']}, shape={decoder_output_shape}")

    runtime = {
        "processor": processor,
        "encoder": encoder_amlnn,
        "decoder": decoder_amlnn,
        "encoder_input_shape": encoder_input_shape,
        "encoder_output_shape": encoder_output_shape,
        "decoder_ids_shape": decoder_ids_shape,
        "decoder_hidden_shape": decoder_hidden_shape,
        "decoder_output_shape": decoder_output_shape,
        "encoder_s": encoder_s,
        "encoder_zp": encoder_zp,
        "encoder_type": encoder_type,
        "decoder_hidden_s": decoder_hidden_s,
        "decoder_hidden_zp": decoder_hidden_zp,
        "decoder_hidden_type": decoder_hidden_type,
        "inference_count": 0
    }

    try:
        print("=" * 60)
        if args.microphone:
            print("Real-time microphone transcription")
            print("=" * 60)
            run_microphone(runtime, args)
        else:
            print(f"Processing audio: {os.path.basename(args.audio_file)}")
            print("=" * 60)
            overlap_samples = OVERLAP_SECONDS * SAMPLE_RATE
            segments = get_audio_segments(
                args.audio_file,
                SAMPLE_RATE,
                TARGET_SAMPLES,
                overlap_samples
            )

            print(f"Segments: {len(segments)}")
            segment_transcriptions = []

            for segment_index, waveform in enumerate(segments, 1):
                print(f"Processing segment [{segment_index}/{len(segments)}]...")
                transcription, language, confidence = transcribe_waveform(
                    waveform,
                    runtime,
                    args.language
                )
                if confidence is not None:
                    print(
                        f"Detected language: {language} "
                        f"(confidence: {confidence:.2%})"
                    )
                segment_transcriptions.append(transcription)

            final_transcription = merge_transcriptions(segment_transcriptions)
            print(f"Transcription: {final_transcription}")

    except Exception as e:
        source = "microphone" if args.microphone else os.path.basename(args.audio_file)
        print(f"Error processing {source}: {e}")

    try:
        print("=" * 60)
        if runtime["inference_count"] > 0:
            print("Encoder performance:")
            print(encoder_amlnn.get_perf_info())
            print("Decoder performance:")
            print(decoder_amlnn.get_perf_info())
        else:
            print("No inference was run; performance data is unavailable.")

        # encoder_amlnn.perf_visualize()
        # decoder_amlnn.perf_visualize()
    finally:
        encoder_amlnn.uninit()
        decoder_amlnn.uninit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
