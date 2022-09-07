import os
import json
import argparse
from loguru import logger
from torch import autocast
from omegaconf import OmegaConf
from diffusers import StableDiffusionPipeline
from kafka import KafkaConsumer


class ImageGenerationConsumerWorker(object):
    def __init__(self, conf):
        super(ImageGenerationConsumerWorker, self).__init__()
        self.conf = OmegaConf.load(conf)

        self.pipe = StableDiffusionPipeline.from_pretrained(self.conf.imagen.checkpoint)
        self.pipe.to(self.conf.imagen.device)

        self.topic = self.conf.kafka.image_generation_topic
        self.kafka_consumer = KafkaConsumer(self.topic,
                                            bootstrap_servers=self.conf.kafka.bootstrap_servers,
                                            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                                            group_id=self.conf.kafka.group_id,
                                            auto_offset_reset="earliest")

        logger.info(self.kafka_consumer.config)
        logger.info(f"ImageGenerationConsumerWorker is live now!!!")

    def synthesize(self, id, prompt):
        logger.info(f"Synthesizing for {id}")
        with autocast("cuda"):
            # TODO: edit in production
            f_name = os.path.join(self.conf.file_server.folder, f"{id}.jpg")
            image = self.pipe(prompt, guidance_scale=7.5)["sample"][0]

            image.save(f_name)
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
