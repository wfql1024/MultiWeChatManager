from inner_utils import *

title("Sound Extract")
print("\n - Extract WAV sound files from WeChat.")

# [Weixin.dll]
dll = dllpath(input(f"\n{BOLD}Weixin.dll{NO_BOLD} (leave blank = auto detect): "))
data = load(dll)
WAV_PATTERN = "RIFF????WAVEfmt"
print(f"\n> Find WAV header")
matches = search(data, WAV_PATTERN)

print(f"\n> Export files")
for i, idx in enumerate(matches):
    length_offset = idx - 4
    length_data = data[length_offset : length_offset + 4]
    wav_length = int.from_bytes(length_data, "big")
    if wav_length > len(data):
        print(f"{YELLOW}[WARN] Invalid WAV length: {wav_length:X}{RESET}")
    wav_data = data[idx : idx + wav_length]
    outpath = f"Sound_{i}_{wav_length:08X}.wav"
    try:
        with open(outpath, "wb") as f:
            f.write(wav_data)
            print(
                f"{GREEN}[√] Sound file at Weixin.dll[{idx:08X}:{idx + wav_length:08X}] -> {outpath}{RESET}"
            )
    except PermissionError:
        print(
            f"{RED}[ERR] The file '{outpath}' is in use, please close it and try again{RESET}"
        )
        pause()
        exit()

pause()
