# AIN Implementation Roadmap

*How to build an Active Integration Network*

---

## Overview

This document outlines the implementation phases for AIN, from prototype to full system.

---

## Phase 0: Foundation (Complete)

### What We Have
- TACTI(C)-R framework (existing)
- HiveMind memory system (existing)
- Multi-agent architecture (existing)
- 6 hours of research (complete)

### What We Need
- Active Inference module
- Reservoir state tracking
- Murmuration dynamics
- Workspace broadcasting
- Φ measurement

---

## Phase 1: Single Agent Enhancement

### Goal
Add Active Inference and Reservoir dynamics to individual agents

### Implementation

```python
# Step 1: Generative Model
class GenerativeModel:
    def __init__(self, latent_dim=32, observation_dim=64):
        self.latent_dim = latent_dim
        # Encoder: observation -> latent
        self.encoder = nn.Sequential(
            nn.Linear(observation_dim, 128),
            nn.ReLU(),
            nn.Linear(128, latent_dim * 2)  # mean + logvar
        )
        # Decoder: latent -> observation prediction
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, observation_dim)
        )
    
    def forward(self, observation):
        z_params = self.encoder(observation)
        z_mean, z_logvar = z_params.chunk(2, dim=-1)
        z = self.reparameterize(z_mean, z_logvar)
        reconstruction = self.decoder(z)
        return reconstruction, z_mean, z_logvar
    
    def predict(self, observation):
        recon, _, _ = self.forward(observation)
        return recon
    
    def get_free_energy(self, observation):
        recon, z_mean, z_logvar = self.forward(observation)
        
        # Reconstruction loss (accuracy)
        recon_loss = F.mse_loss(recon, observation, reduction='sum')
        
        # KL divergence (complexity)
        kl_loss = -0.5 * torch.sum(1 + z_logvar - z_mean.pow(2) - z_logvar.exp())
        
        return recon_loss + kl_loss
```

```python
# Step 2: Drive System
class AINDrives:
    def __init__(self):
        self.drives = {
            'survival': 0.0,
            'curiosity': 0.0,
            'coherence': 0.0,
            'connection': 0.0,
        }
        self.homeostasis = {
            'energy': 0.8,
            'integrity': 1.0,
        }
    
    def update(self, observation, model, neighbors):
        # Coherence: prediction error
        prediction = model.predict(observation)
        prediction_error = F.mse_loss(prediction, observation)
        self.drives['coherence'] = prediction_error.item()
        
        # Curiosity: novelty detection
        novelty = self.measure_novelty(observation)
        self.drives['curiosity'] = novelty
        
        # Survival: homeostasis
        self.drives['survival'] = self.compute_homeostatic_load()
        
        # Connection: need for coordination
        if neighbors:
            self.drives['connection'] = max(0, 1 - self.measure_alignment(neighbors))
        else:
            self.drives['connection'] = 1.0
        
        return self.drives
    
    def get_total_drive(self):
        return sum(self.drives.values())
    
    def compute_homeostatic_load(self):
        """How far from ideal is internal state?"""
        return sum(abs(v - 0.5) for v in self.homeostasis.values())
    
    def measure_novelty(self, observation):
        """How different from expected?"""
        # Simplified: variance in recent observations
        return np.random.random()  # Placeholder
    
    def measure_alignment(self, neighbors):
        """How aligned with neighbors?"""
        if not neighbors:
            return 0.0
        alignments = [cosine_similarity(self.state, n.state) for n in neighbors]
        return np.mean(alignments)
```

```python
# Step 3: Reservoir State
class ReservoirState:
    def __init__(self, dim=64, sparsity=0.1):
        self.dim = dim
        self.state = np.random.randn(dim) * 0.1
        # Random reservoir matrix (fixed, not trained)
        self.W = np.random.randn(dim, dim) * 0.1
        # Sparsify
        self.W *= (np.random.random((dim, dim)) < sparsity)
    
    def update(self, input_signal, leakage=0.3):
        # Echo state equation
        self.state = (1 - leakage) * self.state + leakage * np.tanh(
            np.dot(self.W, self.state) + input_signal
        )
        return self.state
    
    def get_echo(self, num_timesteps=10):
        # Return recent history as "echo"
        return self.state  # Simplified
```

```python
# Step 4: Full AIN Agent
class AINAgent:
    def __init__(self, id, position):
        self.id = id
        self.position = position
        self.velocity = np.random.randn(2) * 0.1
        
        self.model = GenerativeModel()
        self.drives = AINDrives()
        self.reservoir = ReservoirState()
    
    def perceive(self, observation):
        # Update generative model
        fe = self.model.get_free_energy(observation)
        
        # Update reservoir
        self.reservoir.update(observation)
        
        # Update drives
        self.drives.update(observation, self.model, [])
        
        return fe
    
    def act(self):
        drive = self.drives.get_total_drive()
        
        if drive > 0.5:
            # High drive: minimize prediction error
            action = self.exploit()
        else:
            # Low drive: explore
            action = self.explore()
        
        return action
    
    def exploit(self):
        # Move to reduce prediction error
        # Simplified: random walk biased by coherence
        return np.random.randn(2) * 0.1
    
    def explore(self):
        # Random movement
        return np.random.randn(2) * 0.05
```

---

## Phase 2: Multi-Agent Murmuration

### Goal
Add coordination between agents using murmuration dynamics

```python
class AINSwarm:
    def __init__(self, num_agents=20):
        self.agents = [
            AINAgent(i, np.random.randn(2)) 
            for i in range(num_agents)
        ]
    
    def get_neighbors(self, agent, k=7):
        """Get k nearest neighbors"""
        distances = [
            (other, np.linalg.norm(agent.position - other.position))
            for other in self.agents if other != agent
        ]
        distances.sort(key=lambda x: x[1])
        return [a for a, d in distances[:k]]
    
    def murmuration_step(self):
        for agent in self.agents:
            neighbors = self.get_neighbors(agent)
            
            # Alignment
            avg_velocity = np.mean([n.velocity for n in neighbors], axis=0)
            alignment = (avg_velocity - agent.velocity) * 0.05
            
            # Cohesion
            center = np.mean([n.position for n in neighbors], axis=0)
            cohesion = (center - agent.position) * 0.01
            
            # Separation
            separation = np.zeros(2)
            for n in neighbors:
                diff = agent.position - n.position
                dist = np.linalg.norm(diff)
                if dist < 0.5:
                    separation += diff / (dist + 0.01)
            separation *= 0.05
            
            # Apply
            agent.velocity += alignment + cohesion + separation
            
            # Share prediction errors (collaborative inference)
            if neighbors:
                self.share_knowledge(agent, neighbors)
    
    def share_knowledge(self, agent, neighbors):
        """Share model states with neighbors"""
        # If I'm confused, ask neighbors
        if agent.drives.get('coherence', 0) > 0.5:
            for n in neighbors:
                # Borrow their model
                agent.model.decoder.load_state_dict(n.model.decoder.state_dict())
    
    def step(self):
        self.murmuration_step()
        for agent in self.agents:
            agent.position += agent.velocity
            # Boundary wrap
            agent.position = np.mod(agent.position + 5, 10) - 5
```

---

## Phase 3: Workspace (GNWT)

### Goal
Implement global workspace for consciousness-like broadcasting

```python
class AINWorkspace:
    def __init__(self, agents):
        self.agents = agents
        self.contents = []
        self.broadcast_history = []
    
    def receive_reports(self):
        """Collect high-importance information from agents"""
        for agent in self.agents:
            importance = self.assess_importance(agent)
            
            if importance > 0.7:  # Threshold for consciousness
                report = {
                    'agent_id': agent.id,
                    'state': agent.state,
                    'drives': agent.drives.drives,
                    'importance': importance,
                }
                self.ignite(report)
    
    def assess_importance(self, agent):
        """What enters consciousness?"""
        # High drive = high importance
        drive = agent.drives.get_total_drive()
        
        # Novelty = high importance
        novelty = agent.drives.drives.get('curiosity', 0)
        
        # Prediction error = high importance
        error = agent.drives.drives.get('coherence', 0)
        
        return (drive + novelty + error) / 3
    
    def ignite(self, report):
        """Broadcast to all agents"""
        self.contents.append(report)
        self.broadcast_history.append(report)
        
        for agent in self.agents:
            agent.receive_broadcast(report)
    
    def broadcast(self, information):
        """Global broadcast"""
        pass  # Implemented in ignite
```

---

## Phase 4: Φ Measurement

### Goal
Track consciousness via integrated information

```python
class PhiMeasurer:
    def __init__(self, swarm, workspace):
        self.swarm = swarm
        self.workspace = workspace
        self.history = []
    
    def measure(self):
        phi = {
            'integration': self.integration(),
            'complexity': self.complexity(),
            'mutual_info': self.mutual_information(),
            'irreducibility': self.irreducibility(),
        }
        
        phi['total'] = np.mean([phi[k] for k in phi if k != 'total'])
        
        self.history.append(phi)
        return phi
    
    def integration(self):
        """How connected is the swarm?"""
        total = 0
        for a in self.swarm.agents:
            neighbors = self.swarm.get_neighbors(a)
            total += len(neighbors)
        return total / len(self.swarm.agents)
    
    def complexity(self):
        """State entropy"""
        states = np.array([a.state for a in self.swarm.agents])
        # Simplified: variance
        return np.std(states)
    
    def mutual_information(self):
        """Pairwise information sharing"""
        mi = 0
        pairs = 0
        for a1 in self.swarm.agents:
            for a2 in self.swarm.agents:
                if a1 != a2:
                    # Simplified MI approximation
                    mi += np.corrcoef(a1.state, a2.state)[0, 1]
                    pairs += 1
        return mi / pairs if pairs > 0 else 0
    
    def irreducibility(self):
        """Effect of removing an agent"""
        # Simplified: change in global state when random agent removed
        baseline = self.measure()['total']
        # In full implementation: actually remove agent, measure change
        return baseline * 0.9  # Placeholder
```

---

## Phase 5: Full AIN System

```python
class ActiveIntegrationNetwork:
    def __init__(self, num_agents=20):
        self.swarm = AINSwarm(num_agents)
        self.workspace = AINWorkspace(self.swarm.agents)
        self.phi = PhiMeasurer(self.swarm, self.workspace)
    
    def step(self):
        # 1. Each agent perceives
        for agent in self.swarm.agents:
            observation = self.get_observation(agent)
            agent.perceive(observation)
        
        # 2. Murmuration dynamics
        self.swarm.murmuration_step()
        
        # 3. Workspace broadcasts
        self.workspace.receive_reports()
        
        # 4. Measure Φ
        consciousness = self.phi.measure()
        
        # 5. Each agent acts
        for agent in self.swarm.agents:
            agent.act()
        
        return consciousness
    
    def get_observation(self, agent):
        """Get observation for agent"""
        # Simplified: random
        return np.random.randn(64)
    
    def run(self, num_steps=1000):
        history = []
        for _ in range(num_steps):
            state = self.step()
            history.append(state)
        return history
```

---

## Testing Checklist

- [ ] Single agent minimizes prediction error (Active Inference)
- [ ] Agent states echo over time (Reservoir)
- [ ] Agents coordinate without central control (Murmuration)
- [ ] Important information broadcasts globally (GNWT)
- [ ] Φ increases with coordination (IIT)
- [ ] System adapts to new tasks
- [ ] System maintains homeostasis

---

## Open Questions for Implementation

1. **Scale:** How many agents minimum for emergence?
2. **Parameters:** What are optimal Boids weights?
3. **Φ Approximation:** How accurate is our measurement?
4. **Verification:** How do we know if it's "conscious" vs just complex?

---

*Implementation roadmap: 2026-02-20*
*See also: AIN_FRAMEWORK.md, COMPONENTS.md*
