FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
WORKDIR /opt/mmm
COPY requirements/base-ci.txt /tmp/base-ci.txt
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/base-ci.txt
COPY . /opt/mmm
RUN pip install --no-deps --no-build-isolation . \
    && useradd --uid 10001 --create-home mmm \
    && mkdir /artifacts && chown mmm:mmm /artifacts
USER 10001:10001
ENV MMM_DATA_DIR=/artifacts MMM_TRANSPORT=streamable-http MMM_ALLOW_REAL_DATA=false PYTHONDONTWRITEBYTECODE=1
CMD ["python", "deploy/start_http.py"]
