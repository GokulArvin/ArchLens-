FROM python:3.11-slim

# libgl1/libglib2.0-0: required by opencv-python and easyocr for image I/O;
# the rest keep pip builds from falling back to compiling C extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY backend/requirements.txt backend/requirements.txt

# CPU-only torch wheels first (same pinned versions, same approach documented
# in README.md) - this container has no GPU, and the default PyPI wheel pulls
# in multi-GB CUDA runtime packages it would never use.
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 \
    --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r backend/requirements.txt

EXPOSE 8888

CMD ["python", "-m", "jupyter", "lab", "--ip=0.0.0.0", "--port=8888", \
     "--no-browser", "--allow-root", "--IdentityProvider.token=", "--ServerApp.password="]
