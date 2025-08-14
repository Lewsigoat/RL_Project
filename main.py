import pygame, sys, os, objects, math, time
import random
import pickle

from objects import checkpoint1


class CarEnv:
    def __init__(self):
        self.actions = [0, 1, 2]
        self.gamma = 0.95
        self.q_table = {}
        self.current_checkpoint = 0
        self.success = False
        self.steps = 0

        self.finished = 0

        self._on_final_line = False
        self._is_off_track = False
        self._is_on_forbidden_line = False
        self.time = 0


    def reset(self):
        self.success = False
        self.steps = 0

    def apply_action(self,action):
        global ai_left, ai_right
        action = int(action)
        if action == 0:
            ai_left = True
        else:
            ai_left = False
        if action == 2:
            ai_right = True
        else:
            ai_right = False

    def step(self, action, observation, _on_final_line, checkpoint1, checkpoint2, checkpoint3, _is_off_track, _is_on_forbidden_line, current_time):
        self.apply_action(action)
        #self.update_game()

        self._on_final_line = _on_final_line
        self._checkpoint1 = checkpoint1
        self._checkpoint2 = checkpoint2
        self._checkpoint3 = checkpoint3
        self._is_off_track = _is_off_track
        self._is_on_forbidden_line = _is_on_forbidden_line
        self.time = current_time

        reward = 0
        done = False

        if self._checkpoint1 and self.finished < 1:
            reward += 1000
            reward += 500/self.time
            done = True
            self.success = True
            self.finished = 1
            print("halfway finish")

        if self._checkpoint1 and self.finished < 2:
            reward += 10000
            reward += 2500/self.time
            done = True
            self.success = True
            self.finished = 2
            print("halfway finish")

        if self._checkpoint1 and self.finished < 3:
            reward += 50000
            reward += 5000/self.time
            done = True
            self.success = True
            self.finished = 3
            print("halfway finish")

        if self._on_final_line and self.finished < 4:
            reward += 100000000
            reward += 10000/self.time
            done = True
            self.success = True
            self.finished = 24
            print("final finish")

        if self._is_off_track:
            reward -= 1
        else:
            reward += 1
        if self._is_on_forbidden_line:
            reward -= 150
            done = True
            self.success = False
         
#        if self.time > 2:
 #           reward += 0.25
#
 #       if self.time > 60:
  #          reward -= 25
   #         done = True
    #        self.success = False

        obs = observation
        info = {"success": self.success}
        return obs, reward, done, info

    def update(self, state, action, reward, next_state, done, learning_rate=0.1):
        current_q = self.q_table.get((state, action), 0.0)
        max_next_q = 0 if done else max(self.q_table.get((next_state, a), 0.0) for a in self.actions)
        target = reward + self.gamma * max_next_q
        new_q = current_q + learning_rate * (target - current_q)
        self.q_table[(state, action)] = new_q

class QLearningAgent:
    def __init__(self, env, epsilon=1.0, epsilon_min=0.01, epsilon_decay=0.9999):
        self.env = env
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay

    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.choice(self.env.actions)
        return max(self.env.actions, key=lambda a: self.env.q_table.get((state, a), 0.0))

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_min, self.epsilon*self.epsilon_decay)

    def save(self, filename="q_table.pkl"):
        with open(filename, "wb") as f:
            pickle.dump(self.env.q_table, f)

    def load(self, filename="q_table.pkl"):
        with open(filename, "rb") as f:
            self.env.q_table = pickle.load(f)

def train(agent, episodes=500):
    global total_reward, sides, walls, tracks, finish_line
    rewards_history = []
    for episode in range(episodes):
        state = agent.env.reset()
        agent.decay_epsilon()
        #rewards_history.append(total_reward)
        """if len(rewards_history) > 3:
            rewards_history.pop()
        avg_reward_recent = sum(rewards_history)/3
        if avg_reward_recent > total_reward:
            agent.epsilon = agent.epsilon/(agent.epsilon_decay**2)"""
        total_reward = 0
        run(state)
        print(f"Эпизод {episode + 1}/{episodes}, награда: {total_reward:.2f}, epsilon: {agent.epsilon:.3f}")

pygame.init()
pygame.font.init()

width, height = 960, 960
screen = pygame.display.set_mode((width, height))

FPS = 30
SimulatedTimeMultiplier = 25
PYGAME_CLOCK = pygame.time.Clock()

game_font = pygame.font.SysFont("monospace", 24)

sides, walls, tracks, finish_line = [], [], [], []

def read_map(width, height):
    """Reads map.txt and returns coordinates for walls, sides, and tracks."""
    f = open("map.txt", "r")
    sides = []
    walls = []
    tracks = []
    finish = []
    checkpoint1 = []
    checkpoint2 = []
    checkpoint3 = []

    file = f.read().split()
    for i in range(len(file)):
        x_pos = ((i % (width / 30))) * 32
        y_pos = 32 * math.floor(i * 30 / height)

        if file[i] == "1":
            sides.append((x_pos, y_pos))
        if file[i] == "2":
            walls.append((x_pos, y_pos))
        if file[i] == "3":
            tracks.append((x_pos, y_pos))
        if file[i] == "4":
            finish.append((x_pos, y_pos))
        if file[i] == "5":
            checkpoint1.append((x_pos, y_pos))
        if file[i] == "6":
            checkpoint2.append((x_pos, y_pos))
        if file[i] == "7":
            checkpoint3.append((x_pos, y_pos))

    f.close()
    return sides, walls, tracks, finish, checkpoint1, checkpoint2, checkpoint3


def run(state):
    ai = True
    global game_font,FPS,SimulatedTimeMultiplier,screen,agent,total_reward, ai_left, ai_right, sides,walls,tracks,finish_line
    start_time = pygame.time.get_ticks()

    # --- Object Initialization ---
    players = []
    players.append(objects.player(160, 375, 0))

    sidesCoords, wallsCoords, trackCoords, finishCoords, checkpoint1Coords, checkpoint2Coords, checkpoint3Coords = read_map(width, height)
    sides, walls, tracks, finish_line, checkpoint1, checkpoint2, checkpoint3 = [], [], [], [], [], [], []
    for i in sidesCoords:
        sides.append(objects.side(i[0], i[1]))
    for i in wallsCoords:
        walls.append(objects.wall(i[0], i[1]))
    for i in trackCoords:
        tracks.append(objects.track(i[0], i[1]))
    for i in finishCoords:
        finish_line.append(objects.finish(i[0], i[1]))
    for i in checkpoint1Coords:
        checkpoint1.append(objects.finish(i[0], i[1]))
    for i in checkpoint2Coords:
        checkpoint2.append(objects.finish(i[0], i[1]))
    for i in checkpoint3Coords:
        checkpoint3.append(objects.finish(i[0], i[1]))

    wallsCoordsinput = []
    for i in wallsCoords:
        wallsCoordsinput.append(i[0])
        wallsCoordsinput.append(i[1])


    # --- Main Game Loop ---
    playing = True
    while playing:
        # Handle user input and events (quitting, resetting)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print(elapsed_time)
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and not ai:
                    for p in players:
                        p.reset()
                    start_time = pygame.time.get_ticks()

        keys = pygame.key.get_pressed()
        ai_left = False
        ai_right = False

        elapsed_time = (pygame.time.get_ticks() - start_time)*SimulatedTimeMultiplier / (1000)



        # --- Drawing ---
        screen.fill((50, 175, 100))
        for i in sides:
            screen.blit(i.surf, i.rect)
        for i in walls:
            screen.blit(i.surf, i.rect)
        for i in tracks:
            screen.blit(i.surf, i.rect)
        for i in finish_line:
            screen.blit(i.surf, i.rect)
        for i in checkpoint1:
            screen.blit(i.surf, i.rect)
        for i in checkpoint2:
            screen.blit(i.surf, i.rect)
        for i in checkpoint3:
            screen.blit(i.surf, i.rect)

        # --- Player Logic & Drawing ---
        for p in players:
            if not p.game_over:


                collisions = []
                for i in tracks:
                    if i.rect.colliderect(p.rect):
                        collisions.append(["track", i.rect])
                for i in sides:
                    if i.rect.colliderect(p.rect):
                        collisions.append(["side", i.rect])
                for i in walls:
                    if i.rect.colliderect(p.rect):
                        collisions.append(["wall", i.rect])
                for i in finish_line:
                    if i.rect.colliderect(p.rect):
                        if p.movement[1]>0:
                            collisions.append(["finish", i.rect])
                for i in checkpoint1:
                    if i.rect.colliderect(p.rect):
                        if p.movement[0] > 0:
                            collisions.append(["checkpoint1", i.rect])
                for i in checkpoint2:
                    if i.rect.colliderect(p.rect):
                        if p.movement[0] > 0:
                            collisions.append(["checkpoint2", i.rect])
                for i in checkpoint3:
                    if i.rect.colliderect(p.rect):
                        if p.movement[0] > 0:
                            collisions.append(["checkpoint3", i.rect])


                p.collisions(collisions)
                screen.blit(p.surf, p.rect)
            else:
                screen.blit(pygame.image.load("explosion.png"), (p.x, p.y))
                playing = False


        agent.time = elapsed_time
        action = agent.choose_action(state)
        AiInputs = [players[0].x,players[0].y,players[0].direction,players[0].movement[0],players[0].movement[1]]
        for i in wallsCoordsinput:
            AiInputs.append(i)

        next_state, reward, done, _ = agent.env.step(action, tuple(AiInputs), ("finish" in players[0].cols), ("checkpoint1" in players[0].cols),("checkpoint2" in players[0].cols),("checkpoint3" in players[0].cols),("track" in players[0].cols), players[0].out_of_bounds, elapsed_time)
        agent.env.update(state, action, reward, next_state, done)
        state = next_state
        total_reward += reward

        if done:
            playing = False

        p.update(keys, ai_left, ai_right)

        # --- UI Drawing ---
        timer_surface = game_font.render(f"Time: {elapsed_time:.2f}", True, (255, 255, 255))
        screen.blit(timer_surface, (10, 10))

        reset_surface = game_font.render("Press 'R' to reset", True, (255, 255, 255))
        reset_rect = reset_surface.get_rect(topright=(width - 10, 10))
        screen.blit(reset_surface, reset_rect)

        # Update the display and control the frame rate
        pygame.display.flip()
        PYGAME_CLOCK.tick(FPS*SimulatedTimeMultiplier)

    agent.save()

    for i in players:
        i.delete()
    for i in walls:
        i.delete()
    for i in tracks:
        i.delete()
    for i in sides:
        i.delete()
    for i in finish_line:
        i.delete()
    for i in checkpoint1:
        i.delete()
    for i in checkpoint2:
        i.delete()
    for i in checkpoint3:
        i.delete()

total_reward = 0
env = CarEnv()
agent = QLearningAgent(env)

if input("restart (y): ")!="y":
    agent.load()

train(agent, episodes=100000)
