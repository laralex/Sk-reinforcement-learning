from src.critic import Critic
from src.actor import Actor
from src.code_level_optim import CodeLevelOptimizations, StdNormalizer

import src.utility as utility
import gym
import tqdm
import itertools
import torch
import torch.nn as nn

EPISODE_TIME_LIMIT = 1*2048*5

def env_loop(env: gym.Env, config: dict, do_render: bool = False):
   rewards_normalizer = StdNormalizer()
   gamma = config['discount']
   code_level_context = config['code_level_opt']

   n_episodes = max(config['critic']['n_epochs'], config['actor']['n_epochs'])
   n_steps_per_iteration = config['timesteps_per_iteration']

   action_size = len(env.action_space.sample())
   state_size = len(env.observation_space.sample())

   print(f'Action size: {action_size} ; State size: {state_size}')

   # init critic net
   critic = Critic(config['critic'], code_level_context,
      input_size=(action_size + state_size))
   critic_optimizer = torch.optim.AdamW(critic.parameters(),
      lr = config['critic']['lr'], betas=(0.9, 0.999), weight_decay=1e-3)
   critic_scheduler = CodeLevelOptimizations.make_critic_lr_annealing(
      code_level_context, critic_optimizer)

   # init actor net
   actor = Actor(config['actor'], code_level_context,
      input_size=state_size, output_size=action_size)
   actor_optimizer = torch.optim.AdamW(actor.parameters(),
      lr = config['actor']['lr'], betas=(0.9, 0.999), weight_decay=1e-3)
   actor_scheduler = CodeLevelOptimizations.make_actor_lr_annealing(
      code_level_context, critic_optimizer)

   for episode in range(n_episodes):
      state = env.reset()
      state = CodeLevelOptimizations.clip_state(code_level_context, state)
      state = CodeLevelOptimizations.normalize_state(code_level_context, state)
         
      state_buffer = torch.zeros( (n_steps_per_iteration, state_size) )
      action_buffer = torch.zeros( (n_steps_per_iteration, action_size) )
      reward_buffer = torch.zeros( n_steps_per_iteration )
      value_buffer = torch.zeros( n_steps_per_iteration )
      advantage_buffer = torch.zeros( n_steps_per_iteration )
      policy_probability_buffer = torch.zeros( (action_size) )

      timesteps = tqdm.tqdm(range(0, EPISODE_TIME_LIMIT, 5))
      for global_timestep in timesteps:
         timesteps.set_description(f"Episode {episode+1}; Timestep {global_timestep}")

         action = actor.forward(torch.from_numpy(state).float())
         state, reward, done, info = env.step(action.detach().numpy())

         state = CodeLevelOptimizations.clip_state(code_level_context, state)
         state = CodeLevelOptimizations.normalize_state(code_level_context, state)

         rewards_normalizer.add_raw_reward(reward, gamma)
         reward, returns = CodeLevelOptimizations.normalize_rewards(
            code_level_context, rewards_normalizer, gamma, reward, 0.0) # todo returns
         reward = CodeLevelOptimizations.clip_reward(code_level_context, reward)

         step_idx = global_timestep % config['timesteps_per_iteration']

         # first iterations are likely to be done early
         is_done_before_iteration = done and global_timestep < config['timesteps_per_iteration']
         
         # optimize actor-critic networks for the latest portion of episode
         if step_idx == config['timesteps_per_iteration']-1 or is_done_before_iteration:
            critic_optimizer.zero_grad()
            actor_optimizer.zero_grad()

            # compute critic loss
            if episode < config['critic']['n_epochs']:
               #critic_loss = value_buffer.sum()
               #critic_loss.backward()
               pass

            # compute actor loss
            if episode < config['actor']['n_epochs']:
               #actor_loss = value_buffer.sum()
               #actor_loss.backward()
               pass

            global_parameters = itertools.chain(actor.parameters(), critic.parameters())
            CodeLevelOptimizations.clip_gradient(code_level_context, global_parameters)

            critic_optimizer.step()
            actor_optimizer.step()

         if done:
            pass
            #break

         if do_render:
            env.render()
      
      # lr annealing after episode (aka epoch)
      CodeLevelOptimizations.anneal_learning_rate(critic_scheduler)
      CodeLevelOptimizations.anneal_learning_rate(actor_scheduler)

def main():
   args = utility.parse_args()
   config = utility.parse_config(args.config_path)

   print('== CONFIG OF THE EXPERIMENT ==')
   utility.pretty_print(config)

   env = gym.make(config['gym_env'])
   env._max_episode_steps = EPISODE_TIME_LIMIT
   env_loop(env, config, do_render=args.render)
   env.close()

if __name__ == "__main__":
   main()