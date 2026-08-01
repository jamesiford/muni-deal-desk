FROM python:3.14-slim

RUN python -m pip install --no-cache-dir \
    azure-identity==1.25.3 \
    azure-storage-blob==12.28.0

WORKDIR /app
COPY scripts/private_blob_uploader/upload.py ./upload.py
COPY src/corpus/out/os-*.pdf /corpus/
COPY src/corpus/out/cd-*.pdf /corpus/
COPY src/corpus/out/me-*.pdf /corpus/
COPY src/corpus/out/manifest.json /corpus/manifest.json

CMD ["python", "/app/upload.py"]
