import torch
from torch import autocast
from diffusers import StableDiffusionPipeline

device = "cuda"
model_checkpoint = "checkpoints/fp16"

pipe = StableDiffusionPipeline.from_pretrained(model_checkpoint)
# pipe.to(device)

prompt = "a photo of an astronaut riding a horse on mars"
with autocast(device):
    image = pipe(prompt, guidance_scale=7.5)["sample"][0]

image.save("astronaut_rides_horse.png")
