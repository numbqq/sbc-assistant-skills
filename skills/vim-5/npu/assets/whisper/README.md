# Whisper assets for VIM 5

This directory is the self-contained runtime root used by Picoclaw's
`local_voice` channel after the `khadas-vim-5-npu` skill is installed.

- `bin/whisper_demo`: VIM 5 ARM64 JSONL producer linked against the board's
  `libnnsdk.so`.
- `data_bin/`: mel filter and binary tokenizer data used by the C++ runtime.
- `model/`: encoder and decoder ADLA models.
- `tokenizer/`: tokenizer files used by the Python example.

The bundled executable was built on VIM 5 from Whisper repository commit
`1df8a1516322632770c976afec9da4d77cd2e652`. Its C++ source is Apache-2.0.
Rebuild and replace the executable whenever the JSONL protocol or VIM 5 NPU
runtime ABI changes.
