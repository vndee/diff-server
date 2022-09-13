import os
import json
import torch
import argparse
from loguru import logger
# from torch import autocast
from omegaconf import OmegaConf
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from kafka import KafkaConsumer, KafkaProducer


class TextTranslationConsumerWorker(object):
    def __init__(self, conf):
        super(TextTranslationConsumerWorker, self).__init__()
        self.conf = OmegaConf.load(conf)

        self.tokenizer = AutoTokenizer.from_pretrained(self.conf.translator.checkpoint, src_lang="vi_VN")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.conf.translator.checkpoint).to(
            self.conf.translator.device)

        self.topic = self.conf.kafka.text_translation_topic
        self.kafka_consumer = KafkaConsumer(self.topic,
                                            bootstrap_servers=self.conf.kafka.bootstrap_servers,
                                            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                                            group_id=self.conf.kafka.group_id,
                                            auto_offset_reset="earliest",
                                            api_version=(2, 8, 1))

        self.kafka_producer = KafkaProducer(bootstrap_servers=self.conf.kafka.bootstrap_servers,
                                            value_serializer=lambda x: json.dumps(
                                                x, indent=4, sort_keys=True, default=str, ensure_ascii=False
                                            ).encode('utf-8'),
                                            api_version=(2, 8, 1))

        self.imagen_topic = self.conf.kafka.image_generation_topic
        logger.info(self.kafka_consumer.config)
        logger.info(f"TextTranslationConsumerWorker is live now!!!")

    def translate(self, prompt):
        with torch.no_grad():
            input_ids = self.tokenizer(prompt, return_tensors="pt").input_ids
    
            output_ids = self.model.generate(
                input_ids.to(self.conf.translator.device),
                do_sample=True,
                top_k=100,
                top_p=0.8,
                decoder_start_token_id=self.tokenizer.lang_code_to_id["en_XX"],
                num_return_sequences=1,
            )

            en_text = self.tokenizer.batch_decode(output_ids, skip_special_tokens=True)
            en_text = " ".join(en_text)

            return en_text

    def execute(self):
        logger.info(f"Listening on topic: {self.topic}")
        for msg in self.kafka_consumer:
            msg = msg.value
            translated_prompt = self.translate(prompt=msg["prompt"])

            request_id = msg["id"]
            msg["translated_prompt"] = translated_prompt

            try:
                self.kafka_producer.send(self.imagen_topic, msg)
                logger.info(f"Successfully translated {request_id} and sent to {self.imagen_topic}")
            except Exception as ex:
                logger.exception(ex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Diffusion Server")
    parser.add_argument("-f", "--config", default="configs/v1.yaml")
    args = parser.parse_args()

    instance = TextTranslationConsumerWorker(args.config)
    instance.execute()
