# TACTI Architecture Implementation

## Based on: Arousal as Universal Embedding (Nature 2025)

## Core Principle

A single scalar arousal signal can serve as a universal embedding that reconstructs cross-modal, cross-timescale dynamics. This architecture implements that principle.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TACTI SYSTEM ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. AROUSAL SENSOR LAYER                                                    │
│ (Scalar Input: pupil-like measure)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│   │   Physio    │    │  Behavioral │    │   Context   │                  │
│   │  (HRV, EDA, │───▶│  (activity,│───▶│  (time of   │                  │
│   │   pupil)    │    │  movement)  │    │   day)      │                  │
│   └─────────────┘    └─────────────┘    └─────────────┘                  │
│         │                   │                   │                          │
│         └───────────────────┴───────────────────┘                          │
│                             │                                              │
│                    ┌────────▼────────┐                                     │
│                    │  AROUSAL FUSION │  (weighted combination)             │
│                    │   scalar(z,t)   │                                     │
│                    └────────┬────────┘                                     │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. TEMPORAL EMBEDDING LAYER                                                │
│ (Time-delay reconstruction)                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   scalar(z,t) ──▶ [z(t), z(t-τ), z(t-2τ), ..., z(t-dτ)] ──▶ Embedding    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │               DELAY COORDINATE EMBEDDING                     │          │
│   │                                                              │          │
│   │   τ (tau): embedding timescale (seconds)                    │          │
│   │   d: embedding dimension (delay count)                      │          │
│   │                                                              │          │
│   │   Based on Takens' theorem: sufficient d captures            │          │
│   │   full state reconstruction of dynamical system             │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. MANIFOLD PROJECTION LAYER                                               │
│ (Non-linear dimensionality reduction)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                  LATENT MANIFOLD M                           │          │
│   │                                                              │          │
│   │        ┌──────────────────────────────────────┐             │          │
│   │        │    ┌───┐                             │             │          │
│   │        │    │z1 │ ──▶ high-variance axis     │             │          │
│   │        │    └───┘                             │             │          │
│   │        │    ┌───┐                             │             │          │
│   │        │    │z2 │ ──▶ secondary dynamics      │             │          │
│   │        │    └───┘                             │             │          │
│   │        │    ┌───┐                             │             │          │
│   │        │    │z3 │ ──▶ residual variance       │             │          │
│   │        │    └───┘                             │             │          │
│   │        └──────────────────────────────────────┘             │          │
│   │                                                              │          │
│   │   Autoencoder or Diffusion Map                               │          │
│   │   M = f(embedding) where f is non-linear                    │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. CROSS-MODAL DECODER LAYER                                               │
│ (Project manifold to modality-specific states)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐             │
│   │   COGNITION   │    │    EMOTION    │    │   BEHAVIOR    │             │
│   │  ┌─────────┐  │    │  ┌─────────┐  │    │  ┌─────────┐  │             │
│   │  │Working  │  │    │  │ Affective│  │    │  │ Action  │  │             │
│   │  │Memory   │◀─┼────│  │  State   │◀─┼────│  │ Tendency│◀─┼─────m      │
│   │  └─────────┘  │    │  └─────────┘  │    │  └─────────┘  │    │      │
│   └───────────────┘    └───────────────┘    └───────────────┘    │      │
│                                                                      │      │
│   M ───────────────────────────────────────────────────────────────┘      │
│   (shared latent space)                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

## Implementation Details

### Configuration Parameters

```yaml
tacti:
  arousal:
    # Input sources (normalized 0-1)
    sources:
      - physiological: "pupil_normalized"    # or HRV, EDA
      - behavioral: "activity_level"
      - temporal: "circadian_phase"
    
    # Fusion weights
    weights:
      physiological: 0.5
      behavioral: 0.3
      temporal: 0.2
  
  embedding:
    # Timescale in seconds
    tau: 1.0
    
    # Embedding dimension (2d + 1 typical for 3D system)
    dimension: 7
    
    # Update rate (Hz)
    sample_rate: 10
  
  manifold:
    # Latent dimensions
    latent_dim: 3
    
    # Model type: "autoencoder" | "diffusion_map" | "pca"
    model_type: "autoencoder"
    
    # Training
    batch_size: 32
    learning_rate: 0.001
  
  decoders:
    cognition:
      output_dim: 128  # working memory capacity
      layers: [64, 128]
    
    emotion:
      output_dim: 8    # valence, arousal, dominance
      layers: [16, 32]
    
    behavior:
      output_dim: 4    # approach/withdraw/etc
      layers: [8, 16]
```

### Key Algorithms

#### 1. Arousal Fusion
```python
def fuse_arousal(physio, behavioral, temporal, weights):
    return (
        weights['physiological'] * physio +
        weights['behavioral'] * behavioral +
        weights['temporal'] * temporal
    )
```

#### 2. Time-Delay Embedding
```python
def delay_embedding(scalar_series, tau, d):
    """Create delay coordinate embedding."""
    embedded = []
    for i in range(len(scalar_series) - d * tau):
        window = [scalar_series[i + j*tau] for j in range(d)]
        embedded.append(window)
    return np.array(embedded)
```

#### 3. Manifold Learning (Autoencoder)
```python
class ArousalManifoldAE(nn.Module):
    def __init__(self, input_dim, latent_dim):
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, input_dim)
        )
    
    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z), z
```

## Integration Points

### With TACTI-R Principles

1. **Vitality** - Arousal IS the vitality signal
2. **Cognition** - Decoded from manifold projection
3. **Flow** - Continuous temporal embedding
4. **Malleability** - Online learning updates manifold
5. **Agency** - Behavior decoder provides action tendencies

### Therapeutic Applications

- **Biofeedback**: Use arousal manifold to guide intervention
- **Emotional Regulation**: Project current state → adjust arousal → decode new behavior
- **Flow State Detection**: Identify manifold regions associated with optimal performance

## Next Steps

1. Implement sensor layer (mock or real physiological input)
2. Build delay embedding buffer
3. Train autoencoder on synthetic arousal dynamics
4. Test cross-modal reconstruction fidelity
