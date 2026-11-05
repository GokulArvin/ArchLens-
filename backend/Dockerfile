FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV/easyocr. libgl1 is required for cv2 import
# to succeed (libGL.so.1) - confirmed empirically building the P1 CV
# pipeline's own container; the other libs cover broader OpenCV GUI/font
# dependencies.
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 libgl1 git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
