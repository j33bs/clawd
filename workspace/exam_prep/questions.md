# NVIDIA Generative AI LLM Associate - Practice Questions

## Question 1 (Core ML/AI - Easy)
What is the primary purpose of backpropagation in neural networks?

A) To initialize weights randomly
B) To compute gradients and update weights during training
C) To prevent overfitting
D) To accelerate inference

**Answer:** B - Backpropagation computes gradients of the loss with respect to weights, enabling gradient descent optimization.

---

## Question 2 (Prompt Engineering - Easy)
Which prompt engineering technique involves providing a few examples of the desired input-output behavior?

A) Zero-shot prompting
B) Chain-of-thought prompting
C) Few-shot prompting
D) ReAct prompting

**Answer:** C - Few-shot prompting provides 2-5 examples to guide the model's output format/style.

---

## Question 3 (Alignment - Medium)
What does RLHF stand for in LLM training?

A) Reinforced Learning from Human Feedback
B) Reinforcement Learning from Human Feedback
C) Remote Learning from Human Feedback
D) Reinforced Language Human Fine-tuning

**Answer:** B - Reinforcement Learning from Human Feedback uses human preferences to align model outputs with human values.

---

## Question 4 (Data Analysis - Medium)
Which NVIDIA library provides GPU-accelerated data manipulation similar to pandas?

A) TensorFlow
B) RAPIDS cuDF
C) PyTorch
D) NumPy

**Answer:** B - RAPIDS cuDF provides GPU-accelerated DataFrame operations, similar to pandas but on the GPU.

---

## Question 5 (LLM Deployment - Medium)
What is model quantization primarily used for?

A) Increasing model accuracy
B) Reducing model size and memory footprint
C) Training faster
D) Adding new capabilities

**Answer:** B - Quantization reduces model precision (e.g., FP32 → INT8) to decrease size and improve inference speed.

---

## Question 6 (Transformers - Easy)
What is the key innovation of the Transformer architecture?

A) Recurrence
B) Convolutions
C) Self-attention mechanism
D) Gating mechanisms

**Answer:** C - Transformers use self-attention to compute context-dependent representations, enabling parallelization.

---

## Question 7 (Experimentation - Medium)
Which technique helps prevent overfitting by randomly dropping neurons during training?

A) Batch normalization
B) Dropout
C) Early stopping
D) Learning rate scheduling

**Answer:** B - Dropout randomly deactivates neurons during training to improve generalization.

---

## Question 8 (Trustworthy AI - Medium)
Which approach helps mitigate bias in LLM outputs?

A) Increasing model size
B) Fine-tuning on diverse datasets and RLHF
C) Using more compute
D) Longer context windows

**Answer:** B - Diverse training data and human feedback alignment help reduce biased outputs.

---

## Question 9 (Software Dev - Easy)
What is transfer learning?

A) Training from scratch
B) Using a pre-trained model and fine-tuning for a specific task
C) Compressing models
D) Distributed training

**Answer:** B - Transfer learning adapts pre-trained models to new tasks with less data/compute.

---

## Question 10 (LLM Integration - Medium)
What is Retrieval-Augmented Generation (RAG)?

A) A training method for LLMs
B) Combining external knowledge retrieval with LLM generation
C) A model compression technique
D) A prompting framework

**Answer:** B - RAG fetches relevant documents to augment the LLM's context, improving factual accuracy.

---

## Question 11 (Core ML - Hard)
In gradient descent, what does a high learning rate typically cause?

A) Slow convergence
B) Oscillation or divergence
C) Better generalization
D) Less overfitting

**Answer:** B - High learning rates can cause weights to update too drastically, leading to oscillation or divergence.

---

## Question 12 (Prompt Engineering - Hard)
What is the main advantage of ReAct prompting over standard chain-of-thought?

A) It's simpler
B) It combines reasoning with action planning for external tools
C) It uses fewer tokens
D) It requires no examples

**Answer:** B - ReAct interleaves reasoning traces with actions (like tool use), improving complex task handling.

---

## Question 13 (Transformers - Hard)
What is the purpose of positional encodings in Transformers?

A) To add bias terms
B) To give the model information about token order
C) To reduce computation
D) To enable dropout

**Answer:** B - Positional encodings (sinusoidal or learned) encode sequence order since self-attention is position-agnostic.

---

## Question 14 (Deployment - Hard)
Which optimization technique reduces model size by representing weights with fewer bits?

A) Pruning
B) Quantization
C) Knowledge distillation
D) LoRA

**Answer:** B - Quantization maps weights to lower precision (e.g., 32-bit → 8-bit).

---

## Question 15 (Alignment - Hard)
Which method uses a reward model trained on human preferences to fine-tune an LLM?

A) Supervised fine-tuning
B) RLHF
C) In-context learning
D) Prompt tuning

**Answer:** B - RLHF trains a reward model on human rankings and uses RL (PPO) to optimize the LLM.
