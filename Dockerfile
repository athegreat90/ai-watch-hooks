FROM python:3.15.2-slim-trixie@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

# The application uses only the standard library. Remove installer tooling and its vendored packages.
RUN python -m pip uninstall --yes setuptools msgpack urllib3 pip \
    && python -c "import shutil, sysconfig; from pathlib import Path; shutil.rmtree(Path(sysconfig.get_path('stdlib')) / 'ensurepip' / '_bundled', ignore_errors=True)" \
    && python -c "import importlib.util; assert all(importlib.util.find_spec(name) is None for name in ('pip', 'setuptools', 'msgpack', 'urllib3'))"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --chown=1000:1000 bridge/hook.py ./
USER 1000:1000
ENTRYPOINT ["python", "/app/hook.py"]
