FROM python:3.11-slim

# PyTorch (pulled in transitively by sentence-transformers) links
# against libgomp, the GNU OpenMP runtime. python:slim doesn't ship
# it, and importing torch fails with:
#   ImportError: libgomp.so.1: cannot open shared object file
# This is a widely-documented issue on slim Debian base images (hits
# PaddlePaddle, LightGBM, and others the same way) -- fixed here
# proactively rather than discovered later via a cryptic crash.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# requirements.txt is copied and installed BEFORE the rest of the
# source code, deliberately. Docker caches each layer; as long as
# requirements.txt doesn't change, this (slow) install layer is
# reused on every rebuild instead of re-running from scratch just
# because an unrelated .py file changed.
COPY requirements.txt .

# Install the CPU-only build of PyTorch FIRST, from PyTorch's own
# dedicated CPU wheel index. Without this, sentence-transformers'
# dependency on torch resolves to the default PyPI wheel, which
# bundles the full NVIDIA CUDA runtime — several extra gigabytes this
# project has no use for. This container has no GPU, and a similarity
# search over an 11-record corpus wouldn't benefit from one even if
# it did. Installing the CPU build here first means the next line
# finds torch already satisfied and never reaches for the CUDA one.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Bake the retrieval embedding model into the image at build time,
# rather than leaving it to download on first real request. This is
# the standard production pattern for a service depending on a
# third-party model hub: the exact model version is pinned to this
# image build, and the running container has no runtime dependency on
# reaching huggingface.co at all -- important in any environment with
# restricted network egress, and avoids a container's first real
# request paying a multi-second download delay.
#
# This runs as the same user (root, since no USER directive is set --
# fine for a demo image, a real hardening step would add one) that
# will later run the app, so both write to the same cache directory
# and the app finds the model already present at runtime.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000

# --host 0.0.0.0 is required, not optional. uvicorn's default bind
# (127.0.0.1) is only reachable from inside the container itself --
# with the default, `docker run -p 8000:8000` would start cleanly but
# every request from outside would simply hang, since nothing outside
# the container can reach localhost inside it.
#
# --reload is deliberately NOT used here. It's a development
# convenience (watches files on disk, restarts the process) with no
# place in a built image meant to represent a stable running service.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
