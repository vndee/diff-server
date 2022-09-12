FROM nvidia/cuda:10.2-cudnn8-runtime-ubuntu18.04

COPY ./docker/imagen.requirements /requirements.txt

RUN apt-get update -y
RUN apt-get install -y python3 python3-pip
RUN pip3 install --upgrade pip

RUN pip3 install -r /requirements.txt

ENV PYTHONPATH=/app
WORKDIR /app