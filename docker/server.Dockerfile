FROM python:3.8.3-slim

COPY ./docker/server.requirements /requirements.txt
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y tzdata tk-dev apt-utils locales

RUN locale-gen en_US.UTF-8

# set locale
ENV LANG C.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV TZ=Asia/Ho_Chi_Minh

RUN apt-get install -y build-essential software-properties-common gcc g++ musl-dev libpq-dev

RUN pip install --no-cache-dir --upgrade -r /requirements.txt
RUN pip install Pillow

ENV PYTHONPATH=/app
WORKDIR /app
