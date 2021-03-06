import os
import sys

from importlib import import_module

import numpy as np

import torch
import torch.backends.cudnn
from torch.utils.data import DataLoader
from torchvision.transforms import Compose, Normalize

from tqdm import tqdm
from PIL import Image

from robosat_pink.datasets import DatasetTilesBuffer
from robosat_pink.tiles import tiles_from_slippy_map
from robosat_pink.config import load_config
from robosat_pink.colors import make_palette
from robosat_pink.transforms import ImageToTensor
from robosat_pink.web_ui import web_ui


def add_parser(subparser, formatter_class):
    parser = subparser.add_parser(
        "predict", help="Predict masks, from given inputs and an already trained model", formatter_class=formatter_class
    )

    inp = parser.add_argument_group("Inputs")
    inp.add_argument("tiles", type=str, help="tiles directory path [required]")
    inp.add_argument("--checkpoint", type=str, required=True, help="path to trained model to use [required]")
    inp.add_argument("--config", type=str, required=True, help="path to configuration file [required]")
    inp.add_argument("--tile_overlap", type=int, default=64, help="tile pixels overlap [default: 64]")
    inp.add_argument("--tile_size", type=int, help="if set, override tile size value from config file")
    inp.add_argument("--ext_path", type=str, help="path to user's extension dir. Allow to use alternate models.")

    out = parser.add_argument_group("Outputs")
    out.add_argument("out", type=str, help="output directory path [required]")

    perf = parser.add_argument_group("Performances")
    perf.add_argument("--workers", type=int, default=0, help="number of workers to load images [default: 0]")
    perf.add_argument("--batch_size", type=int, help="if set, override batch_size value from config file")

    ui = parser.add_argument_group("Web UI")
    ui.add_argument("--web_ui", action="store_true", help="activate Web UI output")
    ui.add_argument("--web_ui_base_url", type=str, help="alternate Web UI base URL")
    ui.add_argument("--web_ui_template", type=str, help="alternate Web UI template path")

    parser.set_defaults(func=main)


def main(args):
    config = load_config(args.config)
    num_classes = len(config["classes"])
    batch_size = args.batch_size if args.batch_size else config["model"]["batch_size"]
    tile_size = args.tile_size if args.tile_size else config["model"]["tile_size"]

    if torch.cuda.is_available():
        device = torch.device("cuda")
        torch.backends.cudnn.benchmark = True
    else:
        device = torch.device("cpu")

    def map_location(storage, _):
        return storage.cuda() if torch.cuda.is_available() else storage.cpu()

    # https://github.com/pytorch/pytorch/issues/7178
    chkpt = torch.load(args.checkpoint, map_location=map_location)

    if args.ext_path:
        sys.path.append(os.path.expanduser(args.ext_path))

    try:
        model_module = import_module("robosat_pink.models.{}".format(config["model"]["name"]))
    except:
        sys.exit("Unknown {} model".format(config["model"]["name"]))

    std = []
    mean = []
    num_channels = 0
    for channel in config["channels"]:
        std.extend(channel["std"])
        mean.extend(channel["mean"])
        num_channels += len(channel["bands"])

    encoder = config["model"]["encoder"]
    pretrained = config["model"]["pretrained"]

    net = getattr(model_module, "{}".format(config["model"]["name"].title()))(
        num_classes=num_classes, num_channels=num_channels, encoder=encoder, pretrained=pretrained
    ).to(device)
    net = torch.nn.DataParallel(net)
    net.load_state_dict(chkpt["state_dict"])
    net.eval()

    transform = Compose([ImageToTensor(), Normalize(mean=mean, std=std)])
    dataset = DatasetTilesBuffer(args.tiles, transform=transform, size=tile_size, overlap=args.tile_overlap)
    loader = DataLoader(dataset, batch_size=batch_size, num_workers=args.workers)

    palette = make_palette(config["classes"][0]["color"], config["classes"][1]["color"])

    # don't track tensors with autograd during prediction
    with torch.no_grad():
        for images, tiles in tqdm(loader, desc="Eval", unit="batch", ascii=True):
            images = images.to(device)
            outputs = net(images)

            # manually compute segmentation mask class probabilities per pixel
            probs = torch.nn.functional.softmax(outputs, dim=1).data.cpu().numpy()

            for tile, prob in zip(tiles, probs):
                x, y, z = list(map(int, tile))

                # we predicted on buffered tiles; now get back probs for original image
                prob = dataset.unbuffer(prob)

                assert prob.shape[0] == 2, "single channel requires binary model"
                assert np.allclose(np.sum(prob, axis=0), 1.0), "single channel requires probabilities to sum up to one"

                image = np.around(prob[1:, :, :]).astype(np.uint8).squeeze()

                out = Image.fromarray(image, mode="P")
                out.putpalette(palette)

                os.makedirs(os.path.join(args.out, str(z), str(x)), exist_ok=True)
                path = os.path.join(args.out, str(z), str(x), str(y) + ".png")

                out.save(path, optimize=True)

    if args.web_ui:
        template = "leaflet.html" if not args.web_ui_template else args.web_ui_template
        base_url = args.web_ui_base_url if args.web_ui_base_url else "./"
        tiles = [tile for tile, _ in tiles_from_slippy_map(args.tiles)]
        web_ui(args.out, base_url, tiles, tiles, "png", template)
