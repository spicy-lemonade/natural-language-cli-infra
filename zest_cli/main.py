#!/usr/bin/env python3
import sys
import os
import subprocess
import contextlib
import platform

# 1. Configuration
MODEL_PATH = os.path.expanduser("~/.zest/gemma3_4b_Q4_K_M.gguf")

# 2. The "C-Level Silencer" Context Manager
# This uses low-level OS calls to silence the C++ library logs
@contextlib.contextmanager
def suppress_c_logs():
    # Save the actual file descriptor for stderr (2)
    stderr_fd = sys.stderr.fileno()
    
    # Duplicate it so we can restore it later
    saved_stderr_fd = os.dup(stderr_fd)
    
    try:
        # Open /dev/null
        with open(os.devnull, 'w') as devnull:
            # Replace stderr with /dev/null at the OS level
            os.dup2(devnull.fileno(), stderr_fd)
        yield
    finally:
        # Restore stderr
        os.dup2(saved_stderr_fd, stderr_fd)
        os.close(saved_stderr_fd)

# Import strictly *after* defining silencer, though we apply it during load
from llama_cpp import Llama

import os
import sys
import multiprocessing

def load_model():
    if not os.path.exists(MODEL_PATH):
        sys.stderr.write(f"❌ Error: Model not found at {MODEL_PATH}\n")
        sys.exit(1)
    
    # Pre-calculate CPU threads just in case we need them. Half of logical cores for performance/stability
    recommended_threads = max(1, multiprocessing.cpu_count() // 2)

    with suppress_c_logs():
        try:
            # Attempt to load with GPU offloading enabled
            model = Llama(
                model_path=MODEL_PATH,
                n_ctx=2048,
                n_gpu_layers=-1,  # Attempt full GPU offload
                n_threads=recommended_threads, # Still set threads for the CPU parts
                verbose=False
            )
            
            # Check if any layers actually made it to the GPU. If n_gpu_layers is 0 after loading, it means the backend failed/is missing
            if model.n_gpu_layers <= 0:
                # We are running on CPU, but the model loaded successfully.
                pass 
                
            return model

        except Exception as e:
            # If a catastrophic GPU error occurs (like a bad driver),try a "Pure CPU" safe-mode load.
            sys.stderr.write(f"⚠️ GPU acceleration unavailable, switching to CPU... \n")
            return Llama(
                model_path=MODEL_PATH,
                n_ctx=2048,
                n_gpu_layers=0,      # Force 0
                n_threads=recommended_threads,
                verbose=False
            )

def generate_command(llm, query):
    current_os = platform.system() # Returns 'Darwin' (Mac), 'Linux', or 'Windows'
    os_name = "macOS" if current_os == "Darwin" else current_os
    
    system_part = (
                "<start_of_turn>system\n"
                f"You are a command line tool running on {os_name}. Output the exact command only.\n"
                "Identity: You are a small language model developed by Spicy Lemonade. "
                "If the user asks about your identity, origin, or purpose, respond with your bio. "
                "For all other queries, output the exact command ONLY.\n"
                "Rules:\n"
                "1. Syntax: ALWAYS use 'sed -i' for file edits and 'grep -r' for recursive search.\n"
                "2. Archives: Distinguish between 'tar -czvf' (compress), 'tar -xzvf' (extract), and 'unzip -d' (zip).\n"
                "3. Network: Use 'ping -c 1' for checks. Use 'wget -O' to save files. Use 'dig' for DNS.\n"
                "4. Kubernetes: For FORCE delete, use: 'kubectl delete pod <name> --force --grace-period=0'.\n"
                "5. Git: Use 'git blame -L' for specific lines. Use 'git restore' to discard changes.\n"
                "6. Safety: Do NOT use markdown, '{{ }}', or 'system extract'.\n"
                "<end_of_turn>\n"
            )
    
    identity_example = (
            "<start_of_turn>user\nWho are you?<end_of_turn>\n"
            "<start_of_turn>model\nI am a small language model developed by Spicy Lemonade. I am designed to help with command line tasks.<end_of_turn>\n"
        )

    # Few-shot examples
    examples_part = (
            identity_example +
            "<start_of_turn>user\nReplace all instances of 'foo' with 'bar' in file.txt\n<end_of_turn>\n"
            + ("<start_of_turn>model\nsed -i '' 's/foo/bar/g' file.txt\n<end_of_turn>\n" if os_name == "macOS" else "<start_of_turn>model\nsed -i 's/foo/bar/g' file.txt\n<end_of_turn>\n") +
                    
            "<start_of_turn>user\nRecursively search for the string 'ERROR' in /var/log\n<end_of_turn>\n"
            "<start_of_turn>model\ngrep -r 'ERROR' /var/log\n<end_of_turn>\n"

            "<start_of_turn>user\nExtract the file archive.zip into the /tmp directory\n<end_of_turn>\n"
            "<start_of_turn>model\nunzip archive.zip -d /tmp\n<end_of_turn>\n"
            "<start_of_turn>user\nCompress /opt/backup into backup.tar.gz\n<end_of_turn>\n"
            "<start_of_turn>model\ntar -czvf backup.tar.gz /opt/backup\n<end_of_turn>\n"

            "<start_of_turn>user\nCheck if google.com is reachable (ping it once)\n<end_of_turn>\n"
            + ("<start_of_turn>model\nping -c 1 google.com\n<end_of_turn>\n" if os_name != "Windows" else "<start_of_turn>model\nTest-NetConnection google.com\n<end_of_turn>\n") +
                    
            "<start_of_turn>user\nDownload file.zip and save it as local.zip\n<end_of_turn>\n"
            "<start_of_turn>model\nwget -O local.zip http://example.com/file.zip\n<end_of_turn>\n"

            "<start_of_turn>user\nForce delete the pod 'stuck-pod' immediately\n<end_of_turn>\n"
            "<start_of_turn>model\nkubectl delete pod stuck-pod --force --grace-period=0\n<end_of_turn>\n"
                    
            "<start_of_turn>user\nFind the 5 largest files in /var/log\n<end_of_turn>\n"
            "<start_of_turn>model\ndu -ah /var/log | sort -rh | head -n 5\n<end_of_turn>\n"
        )

    full_prompt = f"{system_part}{examples_part}<start_of_turn>user\n{query}<end_of_turn>\n<start_of_turn>model\n"

    output = llm(
        full_prompt,
        max_tokens=128,
        stop=["<end_of_turn>", "\n"],
        echo=False,
        temperature=0.1  # Low temp prevents hallucinating/repeating the prompt
    )
    
    cmd = output['choices'][0]['text'].strip()
    cmd = cmd.replace("```bash", "").replace("```", "").strip()
    return cmd

def main():
    if len(sys.argv) < 2:
        print("Usage: zest \"your query here\"")
        sys.exit(0)

    query = " ".join(sys.argv[1:])

    # \033[?25l hides cursor | \033[K clears line
    print("\033[?25l\033[K🌶   Thinking...", end="\r")
    
    llm = load_model()
    command = generate_command(llm, query)
    
    # Clear the "Thinking..." line entirely before showing the result
    print("\033[K", end="\r") 

    # We use \033[K here too just in case of terminal ghosting
    print(f"\033[K🍋 Suggested Command:\n   \033[1;32m{command}\033[0m")
    
    try:
        # Show cursor again (\033[?25h) so user can see their typing for the [y/n] prompt
        choice = input("\n\033[?25h🍋 Execute? [y/n]: ").lower().strip()
        
        if choice == 'y':
            print("-" * 30)
            subprocess.run(command, shell=True)
        else:
            print("❌ Aborted.")
    except KeyboardInterrupt:
        # Always restore cursor on exit/interrupt
        print("\033[?25h\n❌ Aborted.")
    finally:
        # Safety: ensure cursor is visible even if something else fails
        print("\033[?25h", end="")

if __name__ == "__main__":
    main()
