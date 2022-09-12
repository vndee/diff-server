from diffusers import StableDiffusionPipeline


if __name__ == "__main__":
    pipe = StableDiffusionPipeline.from_pretrained("./checkpoints/fp32")
    pipe = pipe.to("cuda:0")

