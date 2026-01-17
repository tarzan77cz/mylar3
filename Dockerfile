ARG BASE_VERSION=3.8.2-alpine3.11
FROM python:${BASE_VERSION}

# set version label
ARG BASE_VERSION=3.8.2-alpine3.11
ARG MYLAR_COMMIT=v0.3.0
ARG ORG=mylar3
LABEL version="${BASE_VERSION}_${MYLAR_COMMIT}"

RUN \
echo "**** install system packages ****" && \
 apk add --no-cache \
 git \
 # cfscrape dependecies
 nodejs \
 # unrar-cffi & Pillow dependencies
 build-base \
 # unar-cffi dependencies
 libffi-dev \
 # Pillow dependencies
 zlib-dev \
 jpeg-dev \
 # unrar for RAR file processing
 unrar

# Copy local source code instead of cloning from GitHub
WORKDIR /app
COPY . /app/mylar

RUN echo "**** install requirements ****" && \
 pip3 install --no-cache-dir -U -r /app/mylar/requirements.txt && \
 rm -rf ~/.cache/pip/*

# TODO image could be further slimmed by moving python wheel building into a
# build image and copying the results to the final image.

# ports and volumes
VOLUME /config /comics /downloads
EXPOSE 8090
CMD ["python3", "/app/mylar/Mylar.py", "--nolaunch", "--datadir", "/config/mylar"]
