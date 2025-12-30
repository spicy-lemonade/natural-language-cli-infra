#!/usr/bin/env python3
"""
Retry
-----------
- Failed/rejected commands are stored in `failed_history` and excluded from future suggestions.
- Temperature starts at 0.2, increases by 0.15 per rejection (capped at 0.8) to encourage variety.
- Every 2 rejections, user is prompted for additional context to clarify intent.
- Temperature does not reset when user provides additional context, as we want continued exploration.

Execution
---------
- Success = return code 0 (not presence of stdout). Commands like `open`, `mkdir` produce no output.
- Expensive commands (find ~, grep -r /) trigger a warning before execution.

Input
-----
- Yes/no prompts require explicit responses (y/yes/yeah/ok or n/no/nah/nope).
- Queries over 20 words or with vague language ("help me", "urgent") trigger a quality warning.
"""

import sys
import os
import subprocess
import contextlib
import platform
import json
import requests
import time
import multiprocessing
import re
from llama_cpp import Llama

# --- Configuration ---
MODEL_PATH_FP16 = os.path.expanduser("~/.zest/qwen3_4b_fp16.gguf")
MODEL_PATH_Q5 = os.path.expanduser("~/.zest/qwen3_4b_Q5_K_M.gguf")
API_BASE = "https://europe-west1-nl-cli-dev.cloudfunctions.net"
CONFIG_DIR = os.path.expanduser("~/Library/Application Support/Zest")
TOKEN_FILE = os.path.join(CONFIG_DIR, "license.json")
LEASE_DURATION = 1209600  # 14 days in seconds

# Response constants
AFFIRMATIVE = ("y", "yes", "yeah", "yep", "sure", "ok", "okay")
NEGATIVE = ("n", "no", "nah", "nope")


def get_hw_id():
    """Captures the macOS Hardware UUID as per your spec."""
    cmd = 'ioreg -d2 -c IOPlatformExpertDevice | awk -F"\\"" \'/IOPlatformUUID/{print $(NF-1)}\''
    return subprocess.check_output(cmd, shell=True).decode().strip()

def authenticate():
    """The Gatekeeper: Checks local 14-day lease or starts OTP flow."""
    hw_id = get_hw_id()

    # 1. Check for local lease
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                creds = json.load(f)
            
            email = creds.get("email")
            last_verified = creds.get("last_verified", 0)
            current_time = time.time()

            # If the 14-day lease is still valid, bypass network entirely
            if (current_time - last_verified) < LEASE_DURATION:
                return True

            # Lease expired: Attempt silent background refresh
            print("\033[K🌶  Refreshing license...", end="\r")
            try:
                res = requests.post(f"{API_BASE}/validate_device",
                                    json={"email": email, "device_uuid": hw_id},
                                    timeout=4)
                if res.status_code == 200:
                    creds["last_verified"] = current_time
                    with open(TOKEN_FILE, "w") as f:
                        json.dump(creds, f)
                    print("\033[K", end="") # Clear refresh line
                    return True
                elif res.status_code == 403:
                    print(f"\n❌ License revoked or moved: {res.text}")
                    os.remove(TOKEN_FILE)
                    sys.exit(1)
            except requests.exceptions.RequestException:
                # Offline Grace Period: Let them in if server is unreachable
                return True
        except (json.JSONDecodeError, KeyError):
            pass

    # 2. Welcome/OTP Flow (For new devices or expired/revoked licenses)
    print("\n🍋 Welcome to Zest! Activation Required.")
    email = input("Enter your purchase email: ").strip()

    print(f"🌶  Sending code to {email}...", end="\r")
    try:
        otp_res = requests.post(f"{API_BASE}/send_otp", json={"email": email})
        if otp_res.status_code != 200:
            print(f"\n❌ Error: {otp_res.text}")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        sys.exit(1)

    print("\033[K📧 Code sent!")
    code = input("Enter the 6-digit code: ").strip()

    # Get device nickname from system
    nickname = platform.node()

    # Final Verification and Device Registration
    verify_res = requests.post(f"{API_BASE}/verify_otp_and_register",
                            json={
                                "email": email,
                                "otp": code,
                                "device_uuid": hw_id,
                                "device_nickname": nickname
                            })

    if verify_res.status_code == 200:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            json.dump({"email": email, "last_verified": time.time()}, f)
        print("✅ Success! Device linked.")
        return True
    else:
        print(f"❌ Activation failed: {verify_res.text}")
        sys.exit(1)

# --- Query Validation ---

def check_query_quality(query: str) -> tuple[bool, int, bool, bool]:
    """Check if query is too long, vague, or likely shell-mangled."""
    word_count = len(query.split())

    # Suspiciously long queries often indicate shell expansion
    likely_shell_mangled = word_count > 100

    vague_indicators = [
        "help me", "urgent", "trouble", "problem",
        "boss", "deadline", "asap",
        "something like", "or something", "i think", "maybe", "probably",
        "i cant seem", "would you be able", "could you",
        "can you help", "im not sure", "i dont know"
    ]

    query_lower = query.lower()
    has_vague_language = any(indicator in query_lower for indicator in vague_indicators)

    is_good = word_count <= 20 and not has_vague_language and not likely_shell_mangled

    return is_good, word_count, has_vague_language, likely_shell_mangled


def is_expensive_command(command: str) -> tuple[bool, str | None]:
    """Check if a command might be slow or produce excessive output."""
    expensive_patterns = [
        ("find ~", "searching your entire home directory"),
        ("find /", "searching your entire computer"),
        ("grep -r ~", "searching all files in your home directory"),
        ("grep -r /", "searching all files on your computer"),
        ("du -a ~", "calculating size of everything in your home directory"),
        ("du -a /", "calculating size of everything on your computer"),
        ("find . -name", "searching this folder and all nested folders"),
        ("find . -type", "searching this folder and all nested folders"),
    ]

    for pattern, reason in expensive_patterns:
        if pattern in command:
            return True, reason

    return False, None


def clean_command_output(response: str) -> str:
    """
    Clean the model output to extract only the command.
    Handles ChatML tags, markdown, placeholders, and multi-line responses.
    """
    response = response.replace("<|im_end|>", "")
    response = response.replace("<|endoftext|>", "")
    response = response.replace("<|end_of_text|>", "")

    response = response.replace("```bash", "").replace("```sh", "").replace("```", "")

    response = re.sub(r"\[\[\[(.*?)\]\]\]", r"\1", response)
    response = re.sub(r"\[\[(.*?)\]\]", r"\1", response)
    response = re.sub(r"\[-(.*?)-\]", r"\1", response)

    response = " ".join(response.split())

    lines = [line.strip() for line in response.split("\n") if line.strip()]

    if len(lines) > 1:
        has_continuation = any(line.endswith("\\") for line in lines[:-1])
        has_heredoc = any(re.search(r"<<\s*\w+", line) for line in lines)
        has_pipe_continuation = any(line.endswith("|") for line in lines[:-1])

        second_line_is_explanation = (
            len(lines) > 1 and
            (lines[1][0].isupper() or
             any(lines[1].lower().startswith(word) for word in
                 ["this", "the", "it", "note:", "example:", "usage:"]))
        )

        if second_line_is_explanation:
            response = lines[0]
        elif has_continuation or has_heredoc or has_pipe_continuation:
            response = "\n".join(lines)
        else:
            response = lines[0]
    else:
        response = lines[0] if lines else ""

    response = response.replace("`", "").strip()

    return response


def get_os_type() -> str:
    """Get the operating system type for the system prompt."""
    system = platform.system()
    if system == "Darwin":
        return "macOS"
    elif system == "Linux":
        return "Linux"
    elif system == "Windows":
        return "Windows"
    return "Unix"


# --- AI & Execution Logic ---

@contextlib.contextmanager
def suppress_c_logs():
    stderr_fd = sys.stderr.fileno()
    saved_stderr_fd = os.dup(stderr_fd)
    try:
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), stderr_fd)
        yield
    finally:
        os.dup2(saved_stderr_fd, stderr_fd)
        os.close(saved_stderr_fd)


def load_model() -> Llama:
    """Load the LLM model with GPU acceleration fallback to CPU."""
    if os.path.exists(MODEL_PATH_FP16):
        model_path = MODEL_PATH_FP16
    elif os.path.exists(MODEL_PATH_Q5):
        model_path = MODEL_PATH_Q5
    else:
        sys.stderr.write(f"❌ Error: Model not found. Expected one of:\n")
        sys.stderr.write(f"   - {MODEL_PATH_FP16}\n")
        sys.stderr.write(f"   - {MODEL_PATH_Q5}\n")
        sys.exit(1)

    recommended_threads = max(1, multiprocessing.cpu_count() // 2)
    params = {
        "model_path": model_path,
        "n_ctx": 1024,
        "n_batch": 512,
        "n_threads": recommended_threads,
        "verbose": False
    }

    with suppress_c_logs():
        try:
            return Llama(**params, n_gpu_layers=-1)
        except Exception:
            sys.stderr.write("⚠️ GPU acceleration failed, falling back to CPU...\n")
            return Llama(**params, n_gpu_layers=0)

def generate_command(
    llm: Llama,
    query: str,
    history: list[tuple[str, str]] | None = None,
    base_temp: float = 0.2,
    temp_increment: int = 0,
    user_context: str | None = None,
    os_name: str | None = None
) -> str:
    """Generate a CLI command using the LLM with retry-aware temperature scaling."""
    if os_name is None:
        os_name = get_os_type()

    system_prompt = (
        f"You are a specialized CLI assistant for {os_name}. "
        f"Provide only the exact command requested. "
        f"Do not include placeholders, brackets, or explanations. "
        f"Output must be a valid, executable command."
    )

    system_part = f"<|im_start|>system\n{system_prompt}<|im_end|>\n"

    history_context = ""
    if history:
        tried_commands = [cmd for cmd, _ in history]
        history_context = "\n\nDo NOT suggest any of these commands (already tried and rejected):\n"
        for cmd in tried_commands[-5:]:
            history_context += f"- {cmd}\n"
        history_context += "\nProvide a DIFFERENT command."

    additional_context = ""
    if user_context:
        additional_context = f"\n\nAdditional context from user: {user_context}"

    prompt = f"{system_part}<|im_start|>user\n{query}{history_context}{additional_context}<|im_end|>\n<|im_start|>assistant\n"

    temp = min(base_temp + (temp_increment * 0.15), 0.8)

    output = llm(
        prompt,
        max_tokens=120,
        stop=["<|im_end|>", "```", "\n\n", "Try:", "Explanation:", "Instead:"],
        echo=False,
        temperature=temp
    )

    cmd = output["choices"][0]["text"].strip()

    return clean_command_output(cmd)


# --- User Interaction Helpers ---

def prompt_yes_no(message: str) -> bool:
    """
    Prompt user for yes/no input. Re-prompts on ambiguous input.
    Returns True for affirmative, False for negative.
    """
    while True:
        choice = input(message).lower().strip()
        if choice in AFFIRMATIVE:
            return True
        elif choice in NEGATIVE:
            return False
        else:
            print("   Please enter y or n.")


def prompt_for_context(user_context: str | None) -> tuple[str | None, bool]:
    """
    Prompt user for additional context.
    Returns (new_context, was_provided).
    """
    print("\n💡 Having trouble finding the right command?")
    context_input = input("💬 Add context to help? (or 'n' to skip): ").strip()
    if context_input and context_input.lower() not in NEGATIVE:
        return context_input, True
    return user_context, False

def main():
    # 1. Handle Administrative Flags
    if len(sys.argv) > 1:
        flag = sys.argv[1].lower().strip()
        if flag == "--logout":
            if os.path.exists(TOKEN_FILE):
                try:
                    with open(TOKEN_FILE, "r") as f:
                        creds = json.load(f)
                    email = creds.get("email")
                    hw_id = get_hw_id()

                    if email and hw_id:
                        print("🍋 Deregistering device...", end="\r")
                        try:
                            res = requests.post(
                                f"{API_BASE}/deregister_device",
                                json={"email": email, "device_uuid": hw_id},
                                timeout=10
                            )
                            if res.status_code == 200:
                                print("\033[K🍋 Device deregistered from license.")
                            else:
                                print(f"\033[K⚠️  Could not deregister device: {res.text}")
                        except requests.exceptions.RequestException:
                            print("\033[K⚠️  Could not reach server. Device may still be registered.")

                    os.remove(TOKEN_FILE)
                    print("🍋 Logged out successfully.")
                except (json.JSONDecodeError, KeyError):
                    os.remove(TOKEN_FILE)
                    print("🍋 Logged out successfully.")
            else:
                print("🍋 You are not currently logged in.")
            sys.exit(0)
        if flag in ["--help", "-h"]:
            print("Usage: zest \"your query\"")
            print("Flags: --logout")
            sys.exit(0)

    # 2. Guard against empty queries (check before auth to avoid unnecessary auth)
    if len(sys.argv) < 2:
        print("Usage: zest \"your query here\"")
        sys.exit(0)

    query = " ".join(sys.argv[1:])

    # 3. Query quality checks
    is_good_query, word_count, has_vague, likely_mangled = check_query_quality(query)

    if likely_mangled:
        print("⚠️  Your query looks unusually long. This often happens when")
        print("   backticks are interpreted by the shell as commands.")
        print("   Avoid using backticks in your query—use plain text instead.")
        print("   Example: zest \"unzip file.zip without using unzip\"")
        sys.exit(1)

    if not is_good_query:
        print("💡 Tip: Your query might not get the best results.\n")

        if word_count > 20:
            print(f"   Your query has {word_count} words. Try keeping it under 20 words.\n")

        if has_vague:
            print("   Try removing emotional or uncertain language and being more direct.\n")

        print("   Examples of good queries:")
        print("   ✅ 'show Node.js version'")
        print("   ✅ 'find all .jpg files in Downloads'")
        print("   ✅ 'what processes are using the most memory'\n")

        if not prompt_yes_no("🍋 Continue anyway? [y/n]: "):
            print("❌ Aborted. Try rephrasing your query!")
            sys.exit(0)
        print()

    # 4. Licensing Gatekeeper
    authenticate()

    # 5. Load model
    llm = load_model()

    # 6. Core AI Logic with retry loop
    failed_history: list[tuple[str, str]] = []
    user_context: str | None = None
    rejections_since_context = 0
    temp_increment = 0

    while True:
        print(f"\033[?25l\033[K🌶  Thinking...", end="\r")
        command = generate_command(
            llm,
            query,
            history=failed_history,
            base_temp=0.2,
            temp_increment=temp_increment,
            user_context=user_context
        )

        print("\033[K", end="\r")
        print(f"🍋 Suggested Command:\n   \033[1;32m{command}\033[0m")

        is_expensive, reason = is_expensive_command(command)
        if is_expensive:
            print(f"\n⚠️  Warning: This command is {reason}.")
            print("   It might take a while or produce a lot of results.")
            if not prompt_yes_no("🍋 Continue? [y/n]: "):
                rejections_since_context += 1
                failed_history.append((command, "User rejected expensive command"))
                temp_increment += 1

                if rejections_since_context >= 2 and rejections_since_context % 2 == 0:
                    new_context, was_provided = prompt_for_context(user_context)
                    if was_provided:
                        user_context = new_context
                        rejections_since_context = 0
                        print(f"✅ Got it! I'll try again with that context.\n")
                        continue

                if prompt_yes_no("🍋 Try a different command? [y/n]: "):
                    continue
                else:
                    print("❌ Aborted.")
                    break
            print("-" * 30)
        else:
            try:
                if prompt_yes_no("\n\033[?25h🍋 Execute? [y/n]: "):
                    print("-" * 30)
                else:
                    rejections_since_context += 1
                    failed_history.append((command, "User rejected command"))
                    temp_increment += 1

                    if rejections_since_context >= 2 and rejections_since_context % 2 == 0:
                        new_context, was_provided = prompt_for_context(user_context)
                        if was_provided:
                            user_context = new_context
                            rejections_since_context = 0
                            print(f"✅ Got it! I'll try again with that context.\n")
                            continue

                    if prompt_yes_no("🍋 Try a different command? [y/n]: "):
                        continue
                    else:
                        print("❌ Aborted.")
                        break
            except KeyboardInterrupt:
                print("\033[?25h\n❌ Aborted.")
                break

        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True)

            if proc.returncode != 0:
                # Command actually failed
                err_msg = proc.stderr.strip()

                if not err_msg:
                    if "mdfind" in command and len(command.split()) == 1:
                        err_msg = "mdfind requires search criteria. Command is incomplete."
                    elif "grep" in command and "no such file" in proc.stderr.lower():
                        err_msg = "File not found. Check the file path."
                    else:
                        err_msg = f"Command failed with exit code {proc.returncode}. May need different syntax or arguments."

                print(f"\n💡 Note: {err_msg}\n")
                failed_history.append((command, err_msg))
                temp_increment += 1

                if prompt_yes_no("🍋 Try again? [y/n]: "):
                    continue
                else:
                    print("\n💡 Try rephrasing your query or check if the command exists on your system.")
                    break
            else:
                # Command succeeded (return code 0)
                if proc.stdout.strip():
                    print(proc.stdout)
                else:
                    print("✅ Command executed successfully.")
                if proc.stderr.strip():
                    # Some commands write info to stderr even on success
                    print(f"   {proc.stderr.strip()}")
                break
        except KeyboardInterrupt:
            print("\033[?25h\n❌ Aborted.")
            break

    print("\033[?25h", end="")

if __name__ == "__main__":
    main()