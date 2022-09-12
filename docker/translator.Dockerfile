FROM nvidia/cuda:11.1.1-cudnn8-runtime-ubuntu18.04

COPY ./docker/translator.requirements /requirements.txt

RUN apt-get update -y
RUN apt-get install -y python3 python3-pip
RUN pip3 install --upgrade pip

RUN pip3 install -r /requirements.txt
RUN pip3 install torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html

ENV PYTHONPATH=/app
WORKDIR /app
