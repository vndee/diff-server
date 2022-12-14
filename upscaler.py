import os
import gc
import io
import cv2
import json
import redis
import torch
import datetime
import argparse
from PIL import Image
import numpy as np
import sqlalchemy as db
from loguru import logger
from omegaconf import OmegaConf
from kafka import KafkaConsumer
from realesrgan import RealESRGANer
from gfpgan import GFPGANer
from realesrgan.archs.srvgg_arch import SRVGGNetCompact
from basicsr.archs.rrdbnet_arch import RRDBNet


class ImageSuperResolutionConsumerWorker(object):
    def __init__(self, conf):
        super(ImageSuperResolutionConsumerWorker, self).__init__()
        self.conf = OmegaConf.load(conf)

        if self.conf.upscaler.model_name == 'RealESRGAN_x4plus':  # x4 RRDBNet model
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            netscale = 4
        elif self.conf.upscaler.model_name == 'RealESRNet_x4plus':  # x4 RRDBNet model
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            netscale = 4
        elif self.conf.upscaler.model_name == 'RealESRGAN_x4plus_anime_6B':  # x4 RRDBNet model with 6 blocks
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
            netscale = 4
        elif self.conf.upscaler.model_name == 'RealESRGAN_x2plus':  # x2 RRDBNet model
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
            netscale = 2
        elif self.conf.upscaler.model_name == 'realesr-animevideov3':  # x4 VGG-style model (XS size)
            model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4, act_type='prelu')
            netscale = 4
        elif self.conf.upscaler.model_name == 'realesr-general-x4v3':  # x4 VGG-style model (S size)
            model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
            netscale = 4
        
        self.checkpoint_path = os.path.join(self.conf.upscaler.checkpoint, f"{self.conf.upscaler.model_name}.pth")
        self.dni_weight = None

        self.network = RealESRGANer(scale=netscale,
                                    model_path=self.checkpoint_path,
                                    dni_weight=self.dni_weight,
                                    model=model,
                                    tile=self.conf.upscaler.tile,
                                    tile_pad=self.conf.upscaler.tile_pad,
                                    pre_pad=self.conf.upscaler.pre_pad,
                                    half=not self.conf.upscaler.fp32,
                                    gpu_id=self.conf.upscaler.gpu_id)

        self.face_enhancer = GFPGANer(model_path=self.conf.upscaler.face_enhancer_checkpoint,
                                      upscale=self.conf.upscaler.outscale,
                                      arch="clean",
                                      channel_multiplier=2,
                                      bg_upsampler=self.network)

        self.topic = self.conf.kafka.image_super_resolution_topic
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
        logger.info(f"ImageSuperResolutionConsumerWorker is live now!!!")

    def upscaler(self, id):
        with torch.no_grad():
            # TODO: edit in production
            f_name = os.path.join(self.conf.file_server.folder, f"{id}.jpg")
            output = None
            
            if self.rd_connection.exists(id):
                logger.info(f"Image-to-image super-resolution for {id}")
                _data = self.rd_connection.get(id)
                prior_image = Image.open(io.BytesIO(_data)).convert("RGB")          
                img = np.asarray(prior_image)
                img = img[:, :, ::-1].copy()
                
                if len(img.shape) == 3 and img.shape[2] == 4:
                    img_mode = "RGBA"
                else:
                    img_mode = None

                _, _, output = self.face_enhancer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)


            query = db.update(self.pg_query_meta_table).values(
                    is_generated=True, 
                    translated_prompt="-1",
                    updated_at=datetime.datetime.now()).where(
                self.pg_query_meta_table.columns.query_id == str(id))
            _ = self.pg_connection.execute(query)
            
            logger.info(f_name, output.shape)
            cv2.imwrite(f_name, output)
            logger.info(f"Output saved at {f_name}")

        gc.collect()

    def execute(self):
        logger.info(f"Listening on topic: {self.topic}")
        for msg in self.kafka_consumer:
            msg = msg.value
            request_id = msg["id"]
            logger.info(f"Received message with id: {request_id}!")

            try:
                self.upscaler(request_id)
            except Exception as ex:
                logger.exception(ex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Diffusion Server")
    parser.add_argument("-f", "--config", default="configs/v1.yaml")
    args = parser.parse_args()
    
    instance = ImageSuperResolutionConsumerWorker(args.config)
    instance.execute()
