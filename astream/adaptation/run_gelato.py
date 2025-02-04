import time
import sys
from abr_rl_test.maguro_env import MaguroEnv

time.sleep(2)

env = MaguroEnv(model_path=sys.arg[1], server_address=sys.arg[2])
env.env_loop()
