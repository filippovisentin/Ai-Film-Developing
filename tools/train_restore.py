"""Addestra la rete di restauro (rumore, JPEG, sfocatura dello scatto da telefono) ed esporta ONNX.

Uso: python -m tools.train_restore testdata/restore_pairs.npz models/restore_v1.onnx [minuti]
Richiede PyTorch (solo per addestrare; il motore usa poi onnxruntime).
La validazione separa per rullino: nessun rullino compare sia in addestramento sia in verifica.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

PATCH, BATCH = 96, 16


class RestoreNet(nn.Module):
    """Rete residua piccola (~110k parametri): impara solo la correzione da sommare."""

    def __init__(self, ch: int = 48, layers: int = 8):
        super().__init__()
        mods = [nn.Conv2d(3, ch, 3, padding=1), nn.ReLU(inplace=True)]
        for i in range(layers - 2):
            d = 2 if i % 3 == 2 else 1  # qualche strato dilatato: vede i blocchi JPEG da 8 px
            mods += [nn.Conv2d(ch, ch, 3, padding=d, dilation=d), nn.ReLU(inplace=True)]
        mods += [nn.Conv2d(ch, 3, 3, padding=1)]
        self.body = nn.Sequential(*mods)

    def forward(self, x):
        return (x + self.body(x)).clamp(0, 1)


def _roll(name: str) -> str:
    return name.split("-")[0]


def load_pairs(path: Path):
    z = np.load(path, allow_pickle=True)  # file generato da tools.restore_data, non scaricato
    return list(z["inputs"]), list(z["targets"]), [str(n) for n in z["names"]]


def split(names: list[str], val_frac: float = 0.12, seed: int = 0):
    rolls = sorted({_roll(n) for n in names})
    rng = np.random.default_rng(seed)
    val_rolls = set(rng.choice(rolls, max(1, round(len(rolls) * val_frac)), replace=False))
    tr = [i for i, n in enumerate(names) if _roll(n) not in val_rolls]
    va = [i for i, n in enumerate(names) if _roll(n) in val_rolls]
    return tr, va, sorted(val_rolls)


def batch(inputs, targets, idx, rng):
    xs, ys = [], []
    for _ in range(BATCH):
        k = idx[rng.integers(len(idx))]
        a, b = inputs[k], targets[k]
        y0, x0 = rng.integers(a.shape[0] - PATCH), rng.integers(a.shape[1] - PATCH)
        pa, pb = a[y0:y0 + PATCH, x0:x0 + PATCH], b[y0:y0 + PATCH, x0:x0 + PATCH]
        if rng.random() < 0.5:
            pa, pb = pa[:, ::-1], pb[:, ::-1]
        xs.append(pa); ys.append(pb)
    t = lambda v: torch.from_numpy(np.stack(v).astype(np.float32) / 65535).permute(0, 3, 1, 2)  # noqa: E731
    return t(xs), t(ys)


@torch.no_grad()
def val_loss(net, inputs, targets, idx) -> tuple[float, float]:
    net.eval()
    l_net = l_id = 0.0
    for k in idx:
        a = torch.from_numpy(inputs[k].astype(np.float32) / 65535).permute(2, 0, 1)[None]
        b = torch.from_numpy(targets[k].astype(np.float32) / 65535).permute(2, 0, 1)[None]
        l_net += (net(a) - b).abs().mean().item()
        l_id += (a - b).abs().mean().item()
    net.train()
    return l_net / len(idx), l_id / len(idx)


def train(pairs: Path, out: Path, minutes: float = 8.0, seed: int = 0) -> dict:
    torch.manual_seed(seed)
    torch.set_num_threads(os.cpu_count() or 4)
    inputs, targets, names = load_pairs(pairs)
    tr, va, val_rolls = split(names)
    print(f"coppie {len(names)}: addestramento {len(tr)}, verifica {len(va)} (rullini {val_rolls})")
    net = RestoreNet()
    print("parametri:", sum(p.numel() for p in net.parameters()))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    rng = np.random.default_rng(seed)
    t0, step, best = time.time(), 0, (9.0, None)
    budget = minutes * 60
    while time.time() - t0 < budget:
        frac = (time.time() - t0) / budget
        for g in opt.param_groups:
            g["lr"] = 1e-3 * 0.5 * (1 + np.cos(np.pi * frac))
        x, y = batch(inputs, targets, tr, rng)
        loss = (net(x) - y).abs().mean()
        opt.zero_grad(); loss.backward(); opt.step()
        step += 1
        if step % 300 == 0:
            vn, vi = val_loss(net, inputs, targets, va)
            print(f"passo {step:5d}  {time.time() - t0:5.0f}s  verifica L1 rete {vn:.4f}  senza rete {vi:.4f}")
            if vn < best[0]:
                best = (vn, {k: v.clone() for k, v in net.state_dict().items()})
    vn, vi = val_loss(net, inputs, targets, va)
    if vn < best[0]:
        best = (vn, net.state_dict())
    net.load_state_dict(best[1])
    net.eval()
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(net.state_dict(), out.with_suffix(".pt"))  # prima dell'export: i pesi non si perdono
    torch.onnx.export(net, torch.zeros(1, 3, 64, 64), str(out), input_names=["image"],
                      output_names=["restored"], opset_version=17, dynamo=False,
                      dynamic_axes={"image": {2: "h", 3: "w"}, "restored": {2: "h", 3: "w"}})
    report = {"passi": step, "verifica_L1_rete": round(best[0], 5), "verifica_L1_senza": round(vi, 5),
              "rullini_verifica": val_rolls}
    print(report)
    return report


if __name__ == "__main__":
    a = sys.argv[1:]
    train(Path(a[0]), Path(a[1]), float(a[2]) if len(a) > 2 else 8.0)
