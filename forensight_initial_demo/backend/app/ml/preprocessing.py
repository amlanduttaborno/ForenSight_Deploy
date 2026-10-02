from __future__ import annotations

import numpy as np
import torch
from PIL import Image
from torchvision.transforms import functional as TF

IMAGE_SIZE = 384
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def letterbox_pair(image, mask, size=IMAGE_SIZE):
    image = image.convert("RGB")
    mask = mask.convert("L")
    w, h = image.size
    scale = min(size / max(w, 1), size / max(h, 1))
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))

    image_r = image.resize((nw, nh), Image.Resampling.BILINEAR)
    mask_r = mask.resize((nw, nh), Image.Resampling.NEAREST)

    canvas_img = Image.new("RGB", (size, size), color=(0, 0, 0))
    canvas_mask = Image.new("L", (size, size), color=0)
    x0 = (size - nw) // 2
    y0 = (size - nh) // 2
    canvas_img.paste(image_r, (x0, y0))
    canvas_mask.paste(mask_r, (x0, y0))

    meta = {
        "orig_w": w,
        "orig_h": h,
        "new_w": nw,
        "new_h": nh,
        "x0": x0,
        "y0": y0,
    }
    return canvas_img, canvas_mask, meta


def build_inference_inputs(image, caption, clip_processor, size=IMAGE_SIZE):
    """
    Reproduces the final notebook's inference preprocessing:
    RGB -> 384x384 letterbox -> raw [0,1] tensor ->
    ImageNet-normalized RGB tensor + CLIPProcessor inputs.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("image must be a PIL.Image.Image")

    original = image.convert("RGB")
    original_np = np.asarray(original)

    zero_mask = Image.new("L", original.size, color=0)
    model_img, _, meta = letterbox_pair(original, zero_mask, size)

    raw = TF.to_tensor(model_img)
    rgb = TF.normalize(raw, IMAGENET_MEAN, IMAGENET_STD)

    caption = str(caption or "").strip()

    enc = clip_processor(
        images=model_img,
        text=[caption],
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=77,
    )

    batch = {
        "image": rgb.unsqueeze(0),
        "image_raw": raw.unsqueeze(0),
        "clip_pixel_values": enc["pixel_values"],
        "input_ids": enc["input_ids"],
        "attention_mask": enc["attention_mask"],
        "caption_present": torch.tensor([float(bool(caption))], dtype=torch.float32),
    }
    return batch, original_np, meta


def restore_map_to_original(square_map, meta):
    """
    Restores a square 384x384 prediction map to the original image geometry.
    Uses bilinear resize, matching the final notebook's inference logic.
    """
    import cv2

    x0, y0 = meta["x0"], meta["y0"]
    nw, nh = meta["new_w"], meta["new_h"]

    crop = square_map[y0:y0 + nh, x0:x0 + nw]
    return cv2.resize(
        crop,
        (meta["orig_w"], meta["orig_h"]),
        interpolation=cv2.INTER_LINEAR,
    )
