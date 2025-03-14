# Copyright (C) 2024 OpenDLV

FROM python:3.12-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y \
    build-essential \
    cmake \
    software-properties-common \
    protobuf-compiler

RUN pip install --upgrade pip
RUN pip install --upgrade protobuf 
RUN pip install 'eclipse-zenoh==1.2.1'
RUN pip install keelson --verbose numpy 

ADD . /opt/sources
WORKDIR /opt/sources
RUN chmod +x /opt/sources/keelson-opendlv-connector-radar.py
RUN make

ENTRYPOINT ["/opt/sources/keelson-opendlv-connector-radar.py"]
