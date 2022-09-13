FROM nvidia/cuda:11.1.1-cudnn8-runtime-ubuntu20.04

COPY ./docker/translator.requirements /requirements.txt
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -y
RUN apt-get install -y tzdata tk-dev apt-utils locales
RUN locale-gen en_US.UTF-8
ENV LANG C.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV TZ=Asia/Ho_Chi_Minh

RUN apt-get install -y python3 python3-pip
RUN pip3 install --upgrade pip

RUN pip3 install -r /requirements.txt
RUN pip3 install torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html

ENV PYTHONPATH=/app
WORKDIR /app
