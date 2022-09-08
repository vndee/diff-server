import os
import json
import argparse
import sqlalchemy as db
from PIL import Image
from loguru import logger
from torch import autocast
from omegaconf import OmegaConf
from diffusers import StableDiffusionPipeline
from kafka import KafkaConsumer


class ImageGenerationConsumerWorker(object):
    def __init__(self, conf):
        super(ImageGenerationConsumerWorker, self).__init__()
        self.conf = OmegaConf.load(conf)

        # self.pipe = StableDiffusionPipeline.from_pretrained(self.conf.imagen.checkpoint)
        # self.pipe.to(self.conf.imagen.device)

        self.topic = self.conf.kafka.image_generation_topic
        self.kafka_consumer = KafkaConsumer(self.topic,
                                            bootstrap_servers=self.conf.kafka.bootstrap_servers,
                                            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                                            group_id=self.conf.kafka.group_id,
                                            auto_offset_reset="earliest")

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
        logger.info(f"Synthesizing for {id}")
        with autocast("cuda"):
            # TODO: edit in production
            f_name = os.path.join(self.conf.file_server.folder, f"{id}.jpg")
            # image = self.pipe(prompt, guidance_scale=7.5)["sample"][0]
            image = Image.open("static/images/142930455299943375512167784007445374487.jpg")
            image.save(f_name)

            query = db.update(self.pg_query_meta_table).values(is_generated=True).where(
                self.pg_query_meta_table.columns.query_id == str(id))
            _ = self.pg_connection.execute(query)

            logger.info(f"Output saved at {f_name}")

    def execute(self):
        logger.info(f"Listening on topic: {self.topic}")
        for msg in self.kafka_consumer:
            msg = msg.value
            request_id = msg["id"]
            if "translated_prompt" in msg:
                prompt = msg["translated_prompt"]
            else:
                prompt = msg["prompt"]

            logger.info(f"{request_id} {prompt}")
            self.synthesize(request_id, prompt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Diffusion Server")
    parser.add_argument("-f", "--config", default="configs/v1.yaml")
    args = parser.parse_args()

    instance = ImageGenerationConsumerWorker(args.config)
    instance.execute()
