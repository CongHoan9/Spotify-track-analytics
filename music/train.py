"""GPU content representation learning. No invented user listening labels."""
import argparse
import copy
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from music.bundle import save_bundle
from music.data import FEATURES, prepare


class AudioAutoencoder(nn.Module):
    def __init__(self, input_dim, latent_dim=8):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(input_dim, 64), nn.ReLU(), nn.Linear(64, latent_dim))
        self.decoder = nn.Sequential(nn.Linear(latent_dim, 64), nn.ReLU(), nn.Linear(64, input_dim))

    def forward(self, x):
        return self.decoder(self.encoder(x))


def train(csv, output, epochs=30, batch_size=1024, seed=42, require_gpu=False):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if require_gpu and device.type != "cuda":
        raise RuntimeError("Enable Colab Runtime > Change runtime type > GPU")
    print(f"Training on {device}")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    tracks = prepare(csv)
    train_ids, holdout = train_test_split(np.arange(len(tracks)), test_size=.2, random_state=seed)
    valid_ids, test_ids = train_test_split(holdout, test_size=.5, random_state=seed)
    scaler = StandardScaler().fit(tracks.iloc[train_ids][FEATURES])
    values = scaler.transform(tracks[FEATURES]).astype("float32")
    loader = DataLoader(TensorDataset(torch.from_numpy(values[train_ids])),
                        batch_size=batch_size, shuffle=True)
    model = AudioAutoencoder(len(FEATURES)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best, state, history, stale = float("inf"), None, [], 0

    def mse(ids):
        model.eval()
        total = 0.
        with torch.no_grad():
            for batch in np.array_split(ids, max(1, (len(ids) + batch_size - 1) // batch_size)):
                x = torch.from_numpy(values[batch]).to(device)
                total += nn.functional.mse_loss(model(x), x, reduction="sum").item()
        return total / (len(ids) * len(FEATURES))

    for epoch in range(epochs):
        model.train()
        total = 0.
        for (x,) in loader:
            x = x.to(device)
            optimizer.zero_grad(set_to_none=True)
            # Denoising makes the encoder learn a smooth audio representation.
            loss = nn.functional.mse_loss(model(x + .05 * torch.randn_like(x)), x)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(x)
        valid = mse(valid_ids)
        history.append({"epoch": epoch + 1, "train_mse": total / len(train_ids), "validation_mse": valid})
        print(history[-1])
        if valid < best:
            best, state, stale = valid, copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
        if stale >= 5:
            break
    if state is None:
        raise ValueError("Training requires at least one epoch")
    model.load_state_dict(state)
    test = mse(test_ids)
    model.eval()
    with torch.no_grad():
        embeddings = np.concatenate([model.encoder(torch.from_numpy(batch).to(device)).cpu().numpy()
                                     for batch in np.array_split(values, max(1, (len(values)+batch_size-1)//batch_size))])
    torch.save({"state_dict": {k: v.cpu() for k, v in state.items()}, "input_dim": len(FEATURES),
                "latent_dim": 8, "features": FEATURES}, root / "model.pt")
    (root / "scaler.json").write_text(json.dumps({"features": FEATURES, "mean": scaler.mean_.tolist(),
                                                "scale": scaler.scale_.tolist()}), encoding="utf-8")
    metrics = {"validation_mse": best, "test_mse": test, "history": history,
               "note": "Reconstruction quality only; not evidence of user recommendation accuracy."}
    (root / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    np.savez_compressed(root / "split_indices.npz", train=train_ids, validation=valid_ids, test=test_ids)
    save_bundle(root, tracks, embeddings, {"model_type": "audio_autoencoder", "seed": seed,
        "features": FEATURES, "device": str(device), "torch_version": str(torch.__version__),
        "dataset_sha256": hashlib.sha256(Path(csv).read_bytes()).hexdigest()})
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/raw/dataset.csv")
    parser.add_argument("--output", default="artifacts/autoencoder")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--require-gpu", action="store_true")
    args = parser.parse_args()
    train(args.csv, args.output, args.epochs, args.batch_size, require_gpu=args.require_gpu)
