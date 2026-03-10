from PIL import Image
import os

def generate_tiles(image_path, output_dir, tile_size=256, overlap=0):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    os.makedirs(output_dir, exist_ok=True)

    idx = 0
    for y in range(0, h - tile_size + 1, tile_size - overlap):
        for x in range(0, w - tile_size + 1, tile_size - overlap):
            t = img.crop((x, y, x+tile_size, y+tile_size))
            t.save(f"{output_dir}/tile_{idx}.png")
            idx += 1
