import os
import gc
import io
import json
import redis
import torch
import datetime
import argparse
from PIL import Image
import sqlalchemy as db
from loguru import logger
from omegaconf import OmegaConf
from diffusers import StableDiffusionPipeline
from kafka import KafkaConsumer


class ImageGenerationConsumerWorker(object):
    def __init__(self, conf):
        super(ImageGenerationConsumerWorker, self).__init__()
        self.conf = OmegaConf.load(conf)

        self.pipe = StableDiffusionPipeline.from_pretrained(self.conf.imagen.checkpoint)
        self.pipe = self.pipe.to(self.conf.imagen.device)

        self.topic = self.conf.kafka.image_generation_topic
        self.kafka_consumer = KafkaConsumer(self.topic,
                                            bootstrap_servers=self.conf.kafka.bootstrap_servers,
                                            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                                            group_id=self.conf.kafka.group_id,
                                            auto_offset_reset="earliest")

        self.rd_connection = redis.Redis(host=self.conf.redis.host, port=self.conf.redis.port, db=self.conf.redis.database)

        connection_string = f"postgresql://{self.conf.postgres.user}:" \
                            f"{self.conf.postgres.password}@" \
                            f"{self.conf.postgres.host}/{self.conf.postgres.database}"
        self.pg_engine = db.create_engine(connection_string)
        self.pg_connection = self.pg_engine.connect()
        self.pg_query_meta_table = db.Table(self.conf.postgres.query_meta_table,
                                            db.MetaData(),
                                            autoload=True,
                                            autoload_with=self.pg_engine)

        logger.info(self.kafka_consumer.config)
        logger.info(f"ImageGenerationConsumerWorker is live now!!!")

    def synthesize(self, id, prompt):
        with torch.no_grad():
            # TODO: edit in production
            f_name = os.path.join(self.conf.file_server.folder, f"{id}.jpg")
            
            if self.rd_connection.exists(id) is True:
                logger.info(f"Image-to-image synthesizing for {id}")
                _data = self.rd_connection.get(id)
                prior_image = Image.open(io.BytesIO(_data)).convert("RGB")          
                prior_image = prior_image.resize((768, 512))

                _generator = torch.Generator(device=self.conf.imagen.device).manual_seed(1024)
                image = self.pipe(prompt=prompt, init_image=prior_image, strength=0.75, guidance_scale=7.5, generator=_generator).images[0]
            else:
                logger.info(f"Text-to-image synthesizing for {id}")
                image = self.pipe(prompt=prompt, guidance_scale=7.5)["sample"][0]

            # image = Image.open("static/images/10342726256722825098371792010908027558.jpg")
            image.save(f_name)

            query = db.update(self.pg_query_meta_table).values(
                    is_generated=True, 
                    translated_prompt=prompt,
                    updated_at=datetime.datetime.now()).where(
                self.pg_query_meta_table.columns.query_id == str(id))
            _ = self.pg_connection.execute(query)

            logger.info(f"Output saved at {f_name}")

        gc.collect()

    def execute(self):
        logger.info(f"Listening on topic: {self.topic}")
        for msg in self.kafka_consumer:
            msg = msg.value
            request_id = msg["id"]
            if "translated_prompt" in msg:
                prompt = msg["translated_prompt"]
            else:
                prompt = msg["prompt"]

            # TODO: try .. catch
            try:
                self.synthesize(request_id, prompt)
            except Exception as ex:
                logger.exception(ex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Diffusion Server")
    parser.add_argument("-f", "--config", default="configs/v1.yaml")
    args = parser.parse_args()

    instance = ImageGenerationConsumerWorker(args.config)
    instance.execute()
