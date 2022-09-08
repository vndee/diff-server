-- Table: public.query_meta

-- DROP TABLE IF EXISTS public.query_meta;

CREATE TABLE IF NOT EXISTS public.query_meta
(
    query_id character varying COLLATE pg_catalog."default" NOT NULL,
    prompt character varying COLLATE pg_catalog."default" NOT NULL,
    translated_prompt character varying COLLATE pg_catalog."default",
    language character varying COLLATE pg_catalog."default" NOT NULL,
    is_generated boolean NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.query_meta
    OWNER to postgres;