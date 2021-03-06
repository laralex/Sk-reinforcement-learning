from .code_level_optim import CodeLevelOptimizations

import numpy as np
import torch
import torch.nn as nn

class Critic(nn.Module):
   def __init__(self, critic_config, code_level_config, input_size):
      super().__init__()
      self.input_size = input_size
      hidden_layers = critic_config['hidden_layers']
      assert isinstance(hidden_layers, list)

      prev_size = input_size
      self.hidden_layers = []

      self.code_level_context = code_level_config

      for layer_size in hidden_layers:
         layer = nn.Linear(prev_size, layer_size)
         CodeLevelOptimizations.initialize_layer(
            self.code_level_context, layer)
         self.hidden_layers.append(layer)
         prev_size = layer_size

      self.final_layer = nn.Linear(prev_size, 1)
      CodeLevelOptimizations.initialize_layer(
         self.code_level_context, layer, orthogonal_gain=1.0)

   def forward(self, x):
      for layer in self.hidden_layers:
         x = layer(x)
         x = CodeLevelOptimizations.activation_func(
            self.code_level_context, x)

      return self.final_layer(x)

def get_critic_loss():
   return 0.0

def get_advantages(values, rewards, gamma, gae_lambda):
    returns = []
    gae = 0
    returns = np.array(len(rewards))
    for i in reversed(range(len(rewards))):
        delta = rewards[i] + gamma * values[i + 1] - values[i]
        gae = delta + gamma * gae_lambda * gae
        returns[i] = gae + values[i]

    adv = returns - values[:-1]
    return returns, (adv - np.mean(adv)) / (np.std(adv) + 1e-10)