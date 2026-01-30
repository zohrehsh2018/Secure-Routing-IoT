from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import math
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

from scipy.stats import wasserstein_distance
from dtaidistance import dtw


def set_seed(seed: int = 42) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def pick_device(prefer_cuda: bool = True) -> torch.device:
    return torch.device("cuda") if (prefer_cuda and torch.cuda.is_available()) else torch.device("cpu")


def zscore_fit(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mu = X.mean(axis=0)
    sigma = X.std(axis=0) + 1e-8
    return mu, sigma


def zscore_apply(X: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    return (X - mu) / sigma



def phi_norm(d: float, alpha: float = 1.0) -> float:
    return float(1.0 - math.exp(-alpha * max(0.0, d)))


def dtw_distance(F_obs: np.ndarray, F_pred: np.ndarray) -> float:
    s1 = np.linalg.norm(F_obs, axis=1).astype(np.float64)
    s2 = np.linalg.norm(F_pred, axis=1).astype(np.float64)
    return float(dtw.distance(s1, s2))


def wasserstein_seq_distance(F_obs: np.ndarray, F_pred: np.ndarray) -> float:
    D = F_obs.shape[1]
    return float(np.mean([wasserstein_distance(F_obs[:, d], F_pred[:, d]) for d in range(D)]))


# Feature extraction
# f(i,t) = [PFR, Rank, ParentChanges, Velocity]
# x(i,t) = f(i,t) ⊕ weighted_avg_neighbors(f(j,t))

INTRINSIC = ["PFR", "Rank", "ParentChanges", "Velocity"]


def parse_bool_col(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.upper().map({"TRUE": True, "FALSE": False}).fillna(False)


def build_time_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df["timestamp"].dtype == object:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        except Exception:
            pass
    times = sorted(df["timestamp"].unique().tolist())
    tmap = {ts: i for i, ts in enumerate(times)}
    df["t"] = df["timestamp"].map(tmap).astype(int)
    return df


def compute_pfr(row: pd.Series) -> float:
    loss = row.get("packet_loss_rate", np.nan)
    if not pd.isna(loss):
        loss = float(loss)
        pfr = 1.0 - (loss / 100.0) if loss > 1.5 else 1.0 - loss
        return float(np.clip(pfr, 0.0, 1.0))

    rx = float(row.get("app_packet_received", 0.0))
    tx = float(row.get("app_packet_transmitted", 0.0))
    return float(np.clip(tx / max(rx, 1.0), 0.0, 1.0))


def add_intrinsic_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values(["node_id", "t"]).reset_index(drop=True)
    df["Rank"] = df["rank"].astype(float)
    df["PFR"] = df.apply(compute_pfr, axis=1).astype(np.float32)

    parent_changes = np.zeros(len(df), dtype=np.float32)
    velocity = np.zeros(len(df), dtype=np.float32)

    for _node_id, idxs in df.groupby("node_id").groups.items():
        idxs = list(idxs)
        prev = None
        prev_t = None
        for idx in idxs:
            row = df.loc[idx]
            if prev is None:
                parent_changes[idx] = 0.0
                velocity[idx] = 0.0
            else:
                # ParentChanges
                p0 = prev.get("parent_node_id", np.nan)
                p1 = row.get("parent_node_id", np.nan)
                if pd.isna(p0) and pd.isna(p1):
                    parent_changes[idx] = 0.0
                else:
                    parent_changes[idx] = float(int(p0 != p1))

                # Velocity
                dt = float(row["t"] - prev_t) if prev_t is not None else 1.0
                x0, y0 = float(prev["position_x"]), float(prev["position_y"])
                x1, y1 = float(row["position_x"]), float(row["position_y"])
                dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
                velocity[idx] = float(dist / max(dt, 1e-6))

            prev = row
            prev_t = int(row["t"])

    df["ParentChanges"] = parent_changes
    df["Velocity"] = velocity
    return df


def rssi_to_weight(rssi: float, scale: float = 10.0) -> float:
    if np.isnan(rssi):
        return 1.0
    return float(math.exp(float(rssi) / scale))


@dataclass
class SnapshotGraph:
    neighbors: Dict[int, List[Tuple[int, float]]]  # i -> [(j, w_ji), ...]


def build_snapshot_graph(df_t: pd.DataFrame) -> SnapshotGraph:
    neighbors: Dict[int, List[Tuple[int, float]]] = {}
    for _, row in df_t.iterrows():
        i = int(row["node_id"])
        p = row.get("parent_node_id", np.nan)
        if pd.isna(p) or str(p) == "":
            continue
        parent = int(float(p))
        w = rssi_to_weight(float(row.get("rssi", np.nan)))
        neighbors.setdefault(i, []).append((parent, w))
        neighbors.setdefault(parent, []).append((i, w))
    return SnapshotGraph(neighbors=neighbors)


def compute_x_it(df_t: pd.DataFrame, g: SnapshotGraph, node: int) -> np.ndarray:
    row = df_t[df_t["node_id"] == node].iloc[0]
    f_i = row[INTRINSIC].to_numpy(dtype=np.float32)  # [4]

    nbrs = g.neighbors.get(node, [])
    if not nbrs:
        fbar = np.zeros_like(f_i, dtype=np.float32)
    else:
        num = np.zeros_like(f_i, dtype=np.float64)
        den = 0.0
        for j, w in nbrs:
            rj = df_t[df_t["node_id"] == j]
            if rj.empty:
                continue
            f_j = rj.iloc[0][INTRINSIC].to_numpy(dtype=np.float64)
            num += w * f_j
            den += w
        fbar = (num / den).astype(np.float32) if den > 1e-12 else np.zeros_like(f_i, dtype=np.float32)

    return np.concatenate([f_i, fbar], axis=0)  # [8]


def build_x_by_it(df: pd.DataFrame) -> Tuple[Dict[Tuple[int, int], np.ndarray], List[int], List[int]]:
    x_by_it: Dict[Tuple[int, int], np.ndarray] = {}
    times = sorted(df["t"].unique().tolist())
    nodes = sorted(df["node_id"].unique().tolist())

    for t in times:
        df_t = df[df["t"] == t]
        g = build_snapshot_graph(df_t)
        for i in df_t["node_id"].unique():
            i = int(i)
            x_by_it[(i, t)] = compute_x_it(df_t, g, i)

    return x_by_it, times, nodes


def build_sequences(
    x_by_it: Dict[Tuple[int, int], np.ndarray],
    times: List[int],
    nodes: List[int],
    W: int,
    Wp: int,
) -> Tuple[Dict[Tuple[int, int], Tuple[np.ndarray, np.ndarray]], List[Tuple[int, int]]]:
    D = 8
    seq_map: Dict[Tuple[int, int], Tuple[np.ndarray, np.ndarray]] = {}
    keys: List[Tuple[int, int]] = []

    for i in nodes:
        for idx in range(W, len(times) - Wp):
            t_mid = times[idx]
            past = times[idx - W : idx]
            fut = times[idx : idx + Wp]
            if any((i, tt) not in x_by_it for tt in past + fut):
                continue
            X = np.stack([x_by_it[(i, tt)] for tt in past], axis=0).astype(np.float32)
            Y = np.stack([x_by_it[(i, tt)] for tt in fut], axis=0).astype(np.float32)
            seq_map[(i, t_mid)] = (X, Y)
            keys.append((i, t_mid))

    return seq_map, keys



# Seq2Seq model

class EncoderGRU(nn.Module):
    def __init__(self, feat_dim: int, hidden_dim: int, layers: int = 1):
        super().__init__()
        self.gru = nn.GRU(feat_dim, hidden_dim, num_layers=layers, batch_first=True)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h_seq, h_last = self.gru(x)
        return h_seq, h_last


class DecoderGRUWithMHA(nn.Module):
    def __init__(self, feat_dim: int, hidden_dim: int, layers: int = 1, heads: int = 4):
        super().__init__()
        self.gru = nn.GRU(feat_dim, hidden_dim, num_layers=layers, batch_first=True)
        self.mha = nn.MultiheadAttention(embed_dim=hidden_dim, num_heads=heads, batch_first=True)
        self.proj = nn.Linear(hidden_dim, feat_dim)

    def forward(self, y_in: torch.Tensor, h0: torch.Tensor, enc_h: torch.Tensor) -> torch.Tensor:
        dec_h, _ = self.gru(y_in, h0)
        attn, _ = self.mha(dec_h, enc_h, enc_h)
        return self.proj(attn)


class Seq2Seq(nn.Module):
    def __init__(self, feat_dim: int, hidden_dim: int, layers: int = 1, heads: int = 4):
        super().__init__()
        self.enc = EncoderGRU(feat_dim, hidden_dim, layers)
        self.dec = DecoderGRUWithMHA(feat_dim, hidden_dim, layers, heads)

    def forward(self, X: torch.Tensor, y_in: torch.Tensor) -> torch.Tensor:
        enc_h, h_last = self.enc(X)
        return self.dec(y_in, h_last, enc_h)



# Trust equations

def S_rank(i_rank: float, parent_rank: Optional[float], is_sink: bool) -> float:
    return 1.0 if (is_sink or (parent_rank is not None and i_rank > parent_rank)) else 0.0


def S_pfr(pfr: float, theta_pfr: float) -> float:
    return float(math.exp(-max(0.0, (theta_pfr - pfr) / (theta_pfr + 1e-12))))


def T_direct(srank: float, spfr: float, w_rank: float, w_pfr: float) -> float:
    return float(w_rank * srank + w_pfr * spfr)


def T_rep(feedback: List[float]) -> float:
    if not feedback:
        return 0.5
    fb = [float(np.clip(x, 0.0, 1.0)) for x in feedback]
    return float(sum(fb) / len(fb))


def T_model_from_Sdev(Sdev: float, gamma: float = 3.0) -> float:
    return float(math.exp(-gamma * max(0.0, Sdev)))


def T_fused(Tm: float, Td: float, Tr: float, w_model: float, w_direct: float, w_rep: float) -> float:
    return float(np.clip(w_model * Tm + w_direct * Td + w_rep * Tr, 0.0, 1.0))

@dataclass
class HyperParams:
    # sequence lengths
    W: int
    Wp: int

    # model
    hidden: int
    layers: int
    heads: int
    epochs: int
    lr: float
    batch_size: int

    # deviation fusion
    beta: float

    # trust thresholds
    theta_trust: float
    theta_pfr: float

    # trust weights
    w_model: float
    w_direct: float
    w_rep: float
    w_rank: float
    w_pfr: float


class TrustAwarePipeline:
    def __init__(self, hp: HyperParams, prefer_cuda: bool = True, seed: int = 42):
        assert abs(hp.w_model + hp.w_direct + hp.w_rep - 1.0) < 1e-6
        assert abs(hp.w_rank + hp.w_pfr - 1.0) < 1e-6

        self.hp = hp
        self.device = pick_device(prefer_cuda)
        set_seed(seed)

        self.model: Optional[Seq2Seq] = None
        self.mu: Optional[np.ndarray] = None
        self.sigma: Optional[np.ndarray] = None

    def fit_and_score(self, normal_csv: str, attack_csv: str) -> Dict[str, float]:
        # Load
        df_n = pd.read_csv(normal_csv, sep=None, engine="python")
        df_a = pd.read_csv(attack_csv, sep=None, engine="python")

        # optional boolean parsing
        for col in ["attack_active", "is_attacker", "has_geolife"]:
            if col in df_n.columns:
                df_n[col] = parse_bool_col(df_n[col])
            if col in df_a.columns:
                df_a[col] = parse_bool_col(df_a[col])

        df_n["label"] = "normal"
        df_a["label"] = "attack"
        df_all = pd.concat([df_n, df_a], ignore_index=True)

        # Phase A: build x(i,t), sequences
        df_all = build_time_index(df_all)
        df_all = add_intrinsic_features(df_all)
        x_by_it, times, nodes = build_x_by_it(df_all)
        seq_map, keys = build_sequences(x_by_it, times, nodes, self.hp.W, self.hp.Wp)

        # Phase B: train on NORMAL sequences only
        normal_it = set(
            zip(
                df_all[df_all["label"] == "normal"]["node_id"].astype(int).tolist(),
                df_all[df_all["label"] == "normal"]["t"].astype(int).tolist(),
            )
        )
        keys_train = [(i, t_mid) for (i, t_mid) in keys if (i, t_mid) in normal_it]
        if len(keys_train) < 20:
            raise ValueError("Too few normal sequences. Reduce W/Wp or provide more normal timesteps.")

        # Fit z-score on training points
        pts = []
        for k in keys_train:
            X, Y = seq_map[k]
            pts.append(X.reshape(-1, X.shape[-1]))
            pts.append(Y.reshape(-1, Y.shape[-1]))
        pts = np.concatenate(pts, axis=0)
        self.mu, self.sigma = zscore_fit(pts)

        # Model + optimizer
        self.model = Seq2Seq(feat_dim=8, hidden_dim=self.hp.hidden, layers=self.hp.layers, heads=self.hp.heads).to(self.device)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.hp.lr)

        def batch_iter(klist: List[Tuple[int, int]]):
            for s in range(0, len(klist), self.hp.batch_size):
                sub = klist[s : s + self.hp.batch_size]
                Xs, Ys = [], []
                for k in sub:
                    X, Y = seq_map[k]
                    Xs.append(zscore_apply(X, self.mu, self.sigma))
                    Ys.append(zscore_apply(Y, self.mu, self.sigma))
                Xb = torch.tensor(np.stack(Xs, 0), dtype=torch.float32, device=self.device)
                Yb = torch.tensor(np.stack(Ys, 0), dtype=torch.float32, device=self.device)
                yield Xb, Yb

        self.model.train()
        for _ in range(self.hp.epochs):
            for Xb, Yb in batch_iter(keys_train):
                y_in = torch.zeros_like(Yb)
                y_in[:, 1:, :] = Yb[:, :-1, :]
                Y_hat = self.model(Xb, y_in)
                loss = F.mse_loss(Y_hat, Yb)
                opt.zero_grad()
                loss.backward()
                opt.step()

        # Phase C: overall summary only
        return self._overall_summary(df_all, x_by_it, times)

    def _overall_summary(
        self,
        df_all: pd.DataFrame,
        x_by_it: Dict[Tuple[int, int], np.ndarray],
        times: List[int],
    ) -> Dict[str, float]:
        assert self.model is not None and self.mu is not None and self.sigma is not None

        hp = self.hp
        nodes = sorted(df_all["node_id"].unique().tolist())
        seq_map, keys = build_sequences(x_by_it, times, nodes, hp.W, hp.Wp)

        lookup = df_all.set_index(["node_id", "t"])
        graphs_by_t = {t: build_snapshot_graph(df_all[df_all["t"] == t]) for t in times}

        trust_state: Dict[int, float] = {int(n): 1.0 for n in nodes}

        normal_T, attack_T = [], []
        normal_susp, attack_susp = [], []

        self.model.eval()
        with torch.no_grad():
            for (i, t_mid) in keys:
                X, Y = seq_map[(i, t_mid)]
                Xn = zscore_apply(X, self.mu, self.sigma)
                Yn = zscore_apply(Y, self.mu, self.sigma)

                Xb = torch.tensor(Xn[None, ...], dtype=torch.float32, device=self.device)
                Yb = torch.tensor(Yn[None, ...], dtype=torch.float32, device=self.device)

                y_in = torch.zeros_like(Yb)
                y_in[:, 1:, :] = Yb[:, :-1, :]
                Y_hat = self.model(Xb, y_in).detach().cpu().numpy()[0]
                Y_true = Yb.detach().cpu().numpy()[0]

                # Phase 1: model-based trust
                d1 = dtw_distance(Y_true, Y_hat)
                d2 = wasserstein_seq_distance(Y_true, Y_hat)
                Sdev = hp.beta * phi_norm(d1) + (1.0 - hp.beta) * phi_norm(d2)
                Tm = T_model_from_Sdev(Sdev)

                # Phase 2: direct trust
                row_i = lookup.loc[(int(i), int(t_mid))]
                i_rank = float(row_i["Rank"])
                p = row_i.get("parent_node_id", np.nan)
                parent = None if pd.isna(p) or str(p) == "" else int(float(p))
                is_sink = parent is None

                parent_rank = None
                if parent is not None and (parent, int(t_mid)) in lookup.index:
                    parent_rank = float(lookup.loc[(parent, int(t_mid))]["Rank"])

                srank = S_rank(i_rank, parent_rank, is_sink)
                spfr = S_pfr(float(row_i["PFR"]), hp.theta_pfr)
                Td = T_direct(srank, spfr, hp.w_rank, hp.w_pfr)

                # Phase 2: reputation trust (minimal)
                nbrs = graphs_by_t[int(t_mid)].neighbors.get(int(i), [])
                fb = [trust_state.get(int(j), 1.0) for (j, _w) in nbrs]
                Tr = T_rep(fb)

                # Phase 3: fusion + flag
                Tf = T_fused(Tm, Td, Tr, hp.w_model, hp.w_direct, hp.w_rep)
                trust_state[int(i)] = Tf
                suspicious = Tf < hp.theta_trust

                label = row_i.get("label", "unknown")
                if label == "normal":
                    normal_T.append(Tf); normal_susp.append(float(suspicious))
                elif label == "attack":
                    attack_T.append(Tf); attack_susp.append(float(suspicious))

        def safe_mean(x): return float(np.mean(x)) if x else float("nan")
        def safe_rate(x): return float(np.mean(x)) if x else float("nan")

        return 
