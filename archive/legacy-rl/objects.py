import sys

import pygame, math
from pygame.transform import rotate


class player(pygame.sprite.Sprite):
    def __init__(self, x, y, id):
        self.x = x
        self.y = y
        self.original_surf = pygame.image.load("player.png")
        self.surf = self.original_surf
        self.rect = self.surf.get_rect(center = (self.x+16,self.y+16))
        self.direction = 0.0
        self.movement = [0.0,1.0]
        self.max_speed = 5.5
        self.acceleration = 0.25
        self.drag = 0
        self.max_drag = 0
        self.slow = False
        self.excused_frames = 0
        self.last_rot = 0
        self.game_over = False
        self.start_x, self.start_y = x, y
        self.out_of_bounds = False
        self.ai = True

    def delete(self):
        del self

    def update(self, keys, left, right):

        if 0>self.x or self.x>960 or 0>self.y or self.y>960:
            self.game_over = True
            self.out_of_bounds = True

        if (keys[pygame.K_a] and not self.ai) or left:
            self.direction += 3
            self.last_rot = 3

        elif (keys[pygame.K_d] and not self.ai) or right:
            self.direction -= 3
            self.last_rot = -3
        else:
            self.drag -= 0.03
            if self.drag < 0:
                self.drag = 0
        if self.drag > self.max_drag:
            self.drag = self.max_drag

        self.surf = pygame.transform.rotate(self.original_surf, self.direction)
        self.rect = self.surf.get_rect(center = (self.x+16,self.y+16))

        self.movement[0] += math.sin(math.radians(self.direction))*self.acceleration
        self.movement[1] += math.cos(math.radians(self.direction))*self.acceleration
        if math.hypot(self.movement[0], self.movement[1]) > self.max_speed:
            self.movement[0] *= self.max_speed/math.hypot(self.movement[0], self.movement[1])
            self.movement[1] *= self.max_speed/math.hypot(self.movement[0], self.movement[1])
        if self.slow:
            self.drag = 0.7
        self.x += self.movement[0]*(1-self.drag)
        self.y += self.movement[1]*(1-self.drag)

    def collisions(self, collisions):
        self.slow = True
        self.cols = collisions
        for i in collisions:
            if i[0] == "wall":
                self.game_over = True
            if i[0] == "track":
                self.slow = False

    def reset(self):
        """Resets the player to the starting position and state."""
        self.x = self.start_x
        self.y = self.start_y
        self.direction = 0.0
        self.movement = [0.0, 1.0]
        self.surf = pygame.transform.rotate(self.original_surf, self.direction)
        self.rect = self.surf.get_rect(center=(self.x + 16, self.y + 16))

class side(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.Surface((32,32))
        if ((self.x+self.y)/32)%2 != 0:
            self.colour = (255,255,255)
        elif ((self.x+self.y)/32)%2 == 0:
            self.colour = (230,0,0)
        self.surf.fill(self.colour)
        self.rect = self.surf.get_rect(topleft = (x,y))

    def delete(self):
        del self

class wall(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.Surface((32,32))
        self.colour = (50,50,50)
        self.surf.fill(self.colour)
        self.rect = self.surf.get_rect(topleft = (x,y))

    def delete(self):
        del self

class track(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.Surface((32,32))
        self.colour = (100,100,100)
        self.surf.fill(self.colour)
        self.rect = self.surf.get_rect(topleft= (x,y))

    def delete(self):
        del self

class finish(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.image.load("checkerboard.png")
        self.rect = self.surf.get_rect(topleft= (x,y))

    def delete(self):
        del self

class checkpoint1(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.image.load("checkerboard.png")
        self.rect = self.surf.get_rect(topleft= (x,y))

    def delete(self):
        del self

class checkpoint2(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.image.load("checkerboard.png")
        self.rect = self.surf.get_rect(topleft= (x,y))

    def delete(self):
        del self

class checkpoint2(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y
        self.surf = pygame.image.load("checkerboard.png")
        self.rect = self.surf.get_rect(topleft= (x,y))

    def delete(self):
        del self