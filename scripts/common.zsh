# Shared by the Zsh entry points.
repo_root=${0:A:h:h}
if [[ -n ${AI_WATCH_PYTHON:-} ]]; then
    python_command=$AI_WATCH_PYTHON
elif command -v python3.15 >/dev/null 2>&1; then
    python_command=python3.15
else
    python_command=python3
fi
