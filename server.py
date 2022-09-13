import os
import uuid
import json
import argparse
import uvicorn
import sqlalchemy as db
from loguru import logger
from kafka import KafkaProducer
from omegaconf import OmegaConf
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware


class ImageDiffusionServer(object):
    server: FastAPI = FastAPI(title="Image Diffusion Server")

    server.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )

    conf, kafka_producer = None, None

    pg_engine, pg_connection, pg_query_meta_table = None, None, None

    def __init__(self, conf):
        super(ImageDiffusionServer, self).__init__()
        ImageDiffusionServer.conf = OmegaConf.load(conf)
        connection_string = f"postgresql://{ImageDiffusionServer.conf.postgres.user}:" \
                            f"{ImageDiffusionServer.conf.postgres.password}@" \
                            f"{ImageDiffusionServer.conf.postgres.host}/{ImageDiffusionServer.conf.postgres.database}"
        ImageDiffusionServer.pg_engine = db.create_engine(connection_string)
        ImageDiffusionServer.pg_connection = ImageDiffusionServer.pg_engine.connect()
        ImageDiffusionServer.pg_query_meta_table = db.Table(ImageDiffusionServer.conf.postgres.query_meta_table,
                                                            db.MetaData(),
                                                            autoload=True,
                                                            autoload_with=ImageDiffusionServer.pg_engine)

    @staticmethod
    @server.on_event("startup")
    async def startup_event():
        ImageDiffusionServer.kafka_producer = KafkaProducer(
            bootstrap_servers=ImageDiffusionServer.conf.kafka.bootstrap_servers,
            value_serializer=lambda x: json.dumps(
                x, indent=4, sort_keys=True, default=str, ensure_ascii=False
            ).encode('utf-8'),
            api_version=(2, 8, 1))

        logger.info(ImageDiffusionServer.kafka_producer.config)
        logger.info("Service server live now!!!")

    @staticmethod
    @server.get("/healthcheck/", status_code=status.HTTP_200_OK)
    async def healthcheck():
        logger.info("Healthcheck request: alive")
        return {
            "message": "alive",
            "data": 1
        }

    @staticmethod
    @server.get("/text_to_image/", status_code=status.HTTP_201_CREATED)
    async def text_to_image(prompt: str, lang: str):
        prompt = prompt.strip()
        if prompt == "":
            return {
                       "message": "Unaccepted prompt",
                       "data": 0
                   }, status.HTTP_406_NOT_ACCEPTABLE

        request_id = uuid.uuid4().int
        logger.info(f"Received request {request_id}")

        # send to consumer worker
        if lang == "en":
            topic = ImageDiffusionServer.conf.kafka.image_generation_topic
        else:
            topic = ImageDiffusionServer.conf.kafka.text_translation_topic

        try:
            ImageDiffusionServer.kafka_producer.send(topic,
                                                     {
                                                         "id": request_id,
                                                         "prompt": prompt
                                                     })
            logger.info(f"Send request {request_id} to consumer with topic: {topic}")
        except Exception as ex:
            logger.exception(ex)
            return {
                       "message": "Internal Server Error",
                       "data": request_id
                   }, status.HTTP_500_INTERNAL_SERVER_ERROR

        try:
            query = db.insert(ImageDiffusionServer.pg_query_meta_table).values(query_id=request_id,
                                                                               prompt=prompt,
                                                                               translated_prompt=None,
                                                                               language=lang,
                                                                               is_generated=False)
            _ = ImageDiffusionServer.pg_connection.execute(query)
            logger.info(f"Write transaction {request_id} to table {ImageDiffusionServer.conf.postgres.query_meta_table}")
        except Exception as ex:
            logger.exception(ex)
            return {
                       "message": "Internal Server Error",
                       "data": request_id
                   }, status.HTTP_500_INTERNAL_SERVER_ERROR

        return {
                   "message": "We are processing your request",
                   "data": request_id
               }, status.HTTP_102_PROCESSING

    def execute(self):
        uvicorn.run(app=ImageDiffusionServer.server, host=self.conf.server.host, port=self.conf.server.port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Diffusion Server")
    parser.add_argument("-f", "--config", default="configs/v1.yaml")
    args = parser.parse_args()

    instance = ImageDiffusionServer(args.config)
    instance.execute()
