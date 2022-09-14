import argparse
import sqlalchemy as db
from sqlalchemy.sql import func
from loguru import logger
from omegaconf import OmegaConf


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database initialization")
    parser.add_argument("-f", "--config", default="configs/v1.yaml")
    args = parser.parse_args()

    conf = OmegaConf.load(args.config)
    logger.info(conf.postgres)

    connection_string = f"postgresql://{conf.postgres.user}:{conf.postgres.password}@{conf.postgres.host}/{conf.postgres.database}"
    engine = db.create_engine(connection_string)
    connection = engine.connect()
    meta = db.MetaData()

    table = db.Table("query_meta",
                     meta,
                     db.Column("user_id", db.String, nullable=False),
                     db.Column("query_id", db.String, nullable=False),
                     db.Column("prompt", db.String, nullable=False),
                     db.Column("translated_prompt", db.String, nullable=True),
                     db.Column("is_init_image", db.Boolean, nullable=False),
                     db.Column("language", db.String, nullable=False),
                     db.Column("is_generated", db.Boolean, nullable=False, default=False),
                     db.Column("created_at", db.DateTime(timezone=True), default=func.now()),
                     db.Column("updated_at", db.DateTime(timezone=True), default=func.now(), onupdate=func.now()))

    meta.create_all(engine)
    logger.info(f"Created query_meta table.")
